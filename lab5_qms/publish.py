"""CustomizationApi publish + post-publish QM Role seed (T14 / T16 / T25 / V10 / V8 / V14).

Zip never carries Role / UsersInRoles / RolesInGraph (V8 / I.pkg).
`ACU_USER` Quality Manager attach stays e2e-only (V10).
Post-publish seed inserts UsrQMSSetup (QORD QNCR) per company when missing (V14).
Never prints ACU_PASSWORD.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import httpx

from lab5_qms.acu import (
    ACU_INSTANCE_PATH,
    DB_NAME,
    SSH_TIMEOUT,
    AcumaticaClient,
    Instance,
    client,
    list_tenants,
    load_instance,
    ssh_run,
)
from lab5_qms.progress import progress

PACKAGE_NAME = "Lab5.QMS"
QMS_ENDPOINT = "QMS/22.200.001"
QMS_VERSION = "22.200.001"

QM_SCREENS = ("QM101000", "QM201000", "QM301000", "QM302000", "QM401000")
QUALITY_MANAGER_ROLE = "Quality Manager"
QM_RIGHTS_ROLES = ("Administrator", QUALITY_MANAGER_ROLE)
ROLES_IN_GRAPH_COMPANY_ID = 1
ROLES_IN_GRAPH_APPLICATION = "/"
ACCESSRIGHTS_DELETE = 4
QORD = "QORD"
QNCR = "QNCR"
QM401000_DESIGN_ID = "9f9483b9-6427-40c6-9c91-96b22c67c28e"


def instance() -> Instance:
    return load_instance()


def bootstrap_endpoint(session: AcumaticaClient) -> str:
    versions = [ver for name, ver in session.list_endpoints() if name == "Bootstrap"]
    if not versions:
        raise RuntimeError("Bootstrap endpoint not published on this tenant")
    return f"Bootstrap/{max(versions)}"


def company_id() -> int:
    inst = instance()
    for tenant in list_tenants():
        if tenant.login_name.casefold() == inst.tenant.casefold():
            return tenant.company_id
    raise RuntimeError(f"tenant {inst.tenant!r} not in acu tenant list")


def sqlcmd(query: str, timeout: float = SSH_TIMEOUT) -> str:
    inst = instance()
    if not inst.ssh:
        raise RuntimeError("ACU_SSH empty — hosted path has no sqlcmd")
    try:
        r = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                inst.ssh,
                'sqlcmd -S "(local)" -E -C -W -h -1 -s "|" -Q '
                f'"SET NOCOUNT ON; {query}"'
                "\nexit $LASTEXITCODE",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"sqlcmd via ssh timed out after {timeout:.0f}s") from exc
    if r.returncode != 0:
        raise RuntimeError(
            f"remote command failed ({r.returncode}):\n{r.stdout}\n{r.stderr}"
        )
    return r.stdout


def sql_lines(query: str) -> list[str]:
    return [line.strip() for line in sqlcmd(query).splitlines() if line.strip()]


def zip_digest(zip_bytes: bytes) -> str:
    """SHA-256 of every zip member (name + bytes), sorted.

    Publish skip used to hash only project.xml + Bin/Lab5.QMS.dll, so an
    ASPX/SQL-only change looked identical and the tenant kept old pages.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        digest = hashlib.sha256()
        for name in sorted(zf.namelist()):
            if name.endswith("/"):
                continue
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(zf.read(name))
        return digest.hexdigest()


def package_description(zip_bytes: bytes) -> str:
    return (
        "QMS customization 22.200.001; assembly Lab5.QMS.dll; "
        f"zip Lab5_QMS_Customization.zip [sha256:{zip_digest(zip_bytes)}]"
    )


def published_description(session: AcumaticaClient) -> str | None:
    content = session.customization_project_content(PACKAGE_NAME)
    if content is None:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            root = ET.fromstring(zf.read("project.xml"))
    except zipfile.BadZipFile, KeyError, ET.ParseError:
        return None
    return root.get("description")


def _log_tail(status: dict[str, Any], limit: int = 8) -> str:
    log = status.get("log")
    if not isinstance(log, list):
        return ""
    messages = [
        str(entry.get("message", "")) for entry in log if isinstance(entry, dict)
    ]
    return "; ".join(m for m in messages[-limit:] if m)


def drain_publish(session: AcumaticaClient, timeout: float = 120.0) -> None:
    """Finish or fail the in-flight publish before starting another."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = session.customization_publish_end()
        except httpx.TransportError, RuntimeError:
            return
        if status.get("isCompleted") or status.get("isFailed"):
            return
        time.sleep(2.0)


def publish_begin(session: AcumaticaClient, names: list[str]) -> None:
    """Publish named projects without dropping already-published ones."""
    session._checked_log(
        session._http.post(
            "/CustomizationApi/publishBegin",
            json={
                "isMergeWithExistingPackages": True,
                "isOnlyValidation": False,
                "isOnlyDbUpdates": False,
                "isReplayPreviouslyExecutedScripts": False,
                "projectNames": names,
                "tenantMode": "Current",
            },
        )
    )


def wait_published(timeout: float = 600.0, poll: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with client() as session:
                if ("QMS", QMS_VERSION) in session.list_endpoints():
                    return
        except RuntimeError, httpx.TransportError, httpx.HTTPError:
            pass
        time.sleep(poll)
    raise RuntimeError(
        f"{QMS_ENDPOINT} did not appear on GET /entity within {timeout:.0f}s"
    )


def publish_package(zip_bytes: bytes, *, timeout: float = 600.0) -> str:
    """Import + publish Lab5.QMS if the live package digest differs.

    Merges with already-published projects (AcuBootstrap must stay).
    """
    description = package_description(zip_bytes)
    with client() as session:
        with progress("drain in-flight publish", PACKAGE_NAME):
            drain_publish(session)
        names = session.customization_published()
        same = (
            PACKAGE_NAME in names
            and published_description(session) == description
            and ("QMS", QMS_VERSION) in session.list_endpoints()
        )
        with progress("digest skip or import", PACKAGE_NAME) as p:
            if same:
                p.result = "skip"
            else:
                session.customization_import(
                    PACKAGE_NAME, zip_bytes, description=description
                )
                p.result = "import"
        if same:
            return "already published"
        with progress("publishBegin", PACKAGE_NAME):
            publish_begin(session, [PACKAGE_NAME])
        deadline = time.monotonic() + timeout
        with progress("poll publishEnd", PACKAGE_NAME):
            while True:
                try:
                    status = session.customization_publish_end()
                except httpx.TransportError:
                    status = {}
                except RuntimeError:
                    try:
                        session.relogin()
                    except Exception:
                        pass
                    status = {}
                if status.get("isFailed"):
                    detail = _log_tail(status)
                    raise RuntimeError(
                        f"publishing {PACKAGE_NAME} failed"
                        + (f": {detail}" if detail else "")
                    )
                if status.get("isCompleted"):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"publishing {PACKAGE_NAME} did not complete within {timeout:.0f}s"
                    )
                time.sleep(5.0)

    with progress("wait QMS/22.200.001", QMS_ENDPOINT):
        wait_published(timeout=120.0)
    return "published"


def roles_in_graph_rows() -> tuple[tuple[str, str], ...]:
    """(Rolename, ScreenID) pairs for V10 RolesInGraph Delete seed."""
    return tuple((role, screen) for role in QM_RIGHTS_ROLES for screen in QM_SCREENS)


def roles_in_graph_company_ids() -> tuple[int, ...]:
    """CompanyID 1 (shared) plus the live tenant when it differs."""
    ids = [ROLES_IN_GRAPH_COMPANY_ID]
    cid = company_id()
    if cid not in ids:
        ids.append(cid)
    return tuple(ids)


def roles_in_graph_merge_sql(
    company_ids: tuple[int, ...] | None = None,
) -> str:
    """MERGE RolesInGraph Accessrights=4 on QM* for Administrator + Quality Manager."""
    nil = "00000000-0000-0000-0000-000000000000"
    companies = company_ids or (ROLES_IN_GRAPH_COMPANY_ID,)
    values = ", ".join(
        f"({cid}, N'{screen}', N'{role}', "
        f"N'{ROLES_IN_GRAPH_APPLICATION}', {ACCESSRIGHTS_DELETE})"
        for cid in companies
        for role, screen in roles_in_graph_rows()
    )
    return (
        f"DECLARE @mask varbinary(32); "
        f"SELECT TOP 1 @mask = CompanyMask FROM {DB_NAME}.dbo.RolesInGraph "
        f"WHERE CompanyID = {ROLES_IN_GRAPH_COMPANY_ID} "
        f"AND Rolename = N'Administrator'; "
        f"IF @mask IS NULL SET @mask = 0xAAAAAAAA; "
        f"MERGE {DB_NAME}.dbo.RolesInGraph AS t "
        f"USING (VALUES {values}) AS s("
        f"CompanyID, ScreenID, Rolename, ApplicationName, Accessrights) "
        f"ON t.CompanyID = s.CompanyID AND t.ScreenID = s.ScreenID "
        f"AND t.Rolename = s.Rolename AND t.ApplicationName = s.ApplicationName "
        f"WHEN MATCHED AND t.Accessrights <> s.Accessrights THEN "
        f"UPDATE SET Accessrights = s.Accessrights, "
        f"LastModifiedDateTime = GETDATE() "
        f"WHEN NOT MATCHED THEN INSERT ("
        f"CompanyID, ScreenID, Rolename, ApplicationName, Accessrights, "
        f"CompanyMask, CreatedByID, CreatedByScreenID, CreatedDateTime, "
        f"LastModifiedByID, LastModifiedByScreenID, LastModifiedDateTime"
        f") VALUES ("
        f"s.CompanyID, s.ScreenID, s.Rolename, s.ApplicationName, "
        f"s.Accessrights, @mask, '{nil}', 'QM101000', GETDATE(), "
        f"'{nil}', 'QM101000', GETDATE());"
    )


def _sql_nvarchar(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def _ensure_quality_manager_role_row() -> None:
    """Shared Roles row on CompanyID 1 (Bootstrap PUT lands on the tenant)."""
    role = _sql_nvarchar(QUALITY_MANAGER_ROLE)
    sqlcmd(
        "IF NOT EXISTS (SELECT 1 FROM "
        f"{DB_NAME}.dbo.Roles WHERE CompanyID = {ROLES_IN_GRAPH_COMPANY_ID} "
        f"AND Rolename = {role} AND ApplicationName = "
        f"N'{ROLES_IN_GRAPH_APPLICATION}') "
        f"INSERT INTO {DB_NAME}.dbo.Roles ("
        "CompanyID, Rolename, ApplicationName, Descr, Guest, CompanyMask, "
        "CreatedByID, CreatedByScreenID, CreatedDateTime, "
        "LastModifiedByID, LastModifiedByScreenID, LastModifiedDateTime"
        ") SELECT "
        f"{ROLES_IN_GRAPH_COMPANY_ID}, {role}, ApplicationName, "
        "N'QC Hold to Released', 0, CompanyMask, "
        "CreatedByID, 'QM101000', GETDATE(), "
        "LastModifiedByID, 'QM101000', GETDATE() "
        f"FROM {DB_NAME}.dbo.Roles "
        f"WHERE CompanyID = {ROLES_IN_GRAPH_COMPANY_ID} "
        "AND Rolename = N'Administrator' AND ApplicationName = "
        f"N'{ROLES_IN_GRAPH_APPLICATION}'"
    )


def _ensure_qm_roles_in_graph() -> None:
    sqlcmd(roles_in_graph_merge_sql(roles_in_graph_company_ids()))


# 26.101 does not insert nested EntityMapping rows.
QMS_DETAIL_MAPPINGS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "InspectionPlan",
        "Tests",
        "InspectionPlanTest",
        (
            "LineNbr",
            "TestID",
            "Description",
            "TestMethod",
            "TargetValue",
            "MinValue",
            "MaxValue",
            "UOM",
            "Criticality",
        ),
    ),
    (
        "InspectionOrder",
        "Results",
        "InspectionOrderResult",
        (
            "LineNbr",
            "TestID",
            "TestMethod",
            "TargetSpec",
            "ActualNumericValue",
            "ActualTextValue",
            "Evaluation",
            "Notes",
        ),
    ),
)


def expected_qms_detail_mapping_count() -> int:
    return sum(len(fields) for _parent, _coll, _detail, fields in QMS_DETAIL_MAPPINGS)


def qms_detail_mapping_sql(cid: int) -> str:
    """MERGE nested EntityMapping rows for Tests/Results expand and PUT."""
    spec_unions: list[str] = []
    for parent, collection, detail, fields in QMS_DETAIL_MAPPINGS:
        values = ", ".join(
            f"(N'{parent}', N'{collection}', N'{detail}', N'{name}')" for name in fields
        )
        spec_unions.append(
            f"SELECT Parent, Collection, Detail, FieldName FROM (VALUES {values}) "
            "AS v(Parent, Collection, Detail, FieldName)"
        )
    spec = " UNION ALL ".join(spec_unions)
    db = DB_NAME
    return (
        f"DECLARE @cid int = {cid}; "
        "DECLARE @mask varbinary(32); "
        f"SELECT TOP 1 @mask = CompanyMask FROM {db}.dbo.EntityMapping "
        "WHERE CompanyID = @cid; "
        "IF @mask IS NULL SET @mask = 0xAAAAAAAA; "
        "DECLARE @src TABLE ("
        "CompanyID int, MappingKey nvarchar(255), "
        "MappedObject nvarchar(128), MappedField nvarchar(128)); "
        "INSERT INTO @src (CompanyID, MappingKey, MappedObject, MappedField) "
        "SELECT @cid, "
        "N'E/' + CAST(p.EntityId AS varchar(20)) + N'/' "
        "+ CAST(cf.EntityFieldId AS varchar(20)) + N'/' "
        "+ CAST(d.EntityId AS varchar(20)) + N'/' "
        "+ CAST(df.EntityFieldId AS varchar(20)), "
        "s.Collection, s.FieldName "
        f"FROM ({spec}) AS s "
        f"CROSS APPLY (SELECT TOP 1 EntityId FROM {db}.dbo.EntityDescription "
        "WHERE InterfaceName = N'QMS' AND ObjectName = s.Parent "
        "AND CompanyID IN (@cid, 1) "
        "ORDER BY CASE WHEN CompanyID = @cid THEN 0 ELSE 1 END) p "
        f"CROSS APPLY (SELECT TOP 1 EntityId FROM {db}.dbo.EntityDescription "
        "WHERE InterfaceName = N'QMS' AND ObjectName = s.Detail "
        "AND CompanyID IN (@cid, 1) "
        "ORDER BY CASE WHEN CompanyID = @cid THEN 0 ELSE 1 END) d "
        f"CROSS APPLY (SELECT TOP 1 EntityFieldId FROM {db}.dbo.EntityFieldDescription "
        "WHERE EntityId = p.EntityId AND FieldName = s.Collection "
        "AND CompanyID IN (@cid, 1) "
        "ORDER BY CASE WHEN CompanyID = @cid THEN 0 ELSE 1 END) cf "
        f"CROSS APPLY (SELECT TOP 1 EntityFieldId FROM {db}.dbo.EntityFieldDescription "
        "WHERE EntityId = d.EntityId AND FieldName = s.FieldName "
        "AND CompanyID IN (@cid, 1) "
        "ORDER BY CASE WHEN CompanyID = @cid THEN 0 ELSE 1 END) df; "
        f"DECLARE @before int = (SELECT COUNT(*) FROM {db}.dbo.EntityMapping t "
        "INNER JOIN @src s ON t.CompanyID = s.CompanyID AND t.MappingKey = s.MappingKey); "
        f"MERGE {db}.dbo.EntityMapping AS t "
        "USING @src AS s ON t.CompanyID = s.CompanyID AND t.MappingKey = s.MappingKey "
        "WHEN NOT MATCHED THEN INSERT ("
        "CompanyID, CompanyMask, MappingKey, MappedObject, MappedField"
        ") VALUES (s.CompanyID, @mask, s.MappingKey, s.MappedObject, s.MappedField); "
        "DECLARE @inserted int = @@ROWCOUNT; "
        f"DECLARE @after int = (SELECT COUNT(*) FROM {db}.dbo.EntityMapping t "
        "INNER JOIN @src s ON t.CompanyID = s.CompanyID AND t.MappingKey = s.MappingKey); "
        "SELECT @before, @inserted, @after;"
    )


def _parse_mapping_seed_counts(out: str) -> tuple[int, int, int]:
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("EntityMapping seed: empty sqlcmd output")
    parts = lines[-1].split("|")
    if len(parts) != 3:
        raise RuntimeError(
            f"EntityMapping seed: expected before|inserted|after, got {out!r}"
        )
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise RuntimeError(
            f"EntityMapping seed: non-int sqlcmd output {out!r}"
        ) from exc


def _ensure_qms_detail_mappings() -> int:
    """Insert nested Tests/Results EntityMapping rows. Return 1 if recycle needed."""
    expected = expected_qms_detail_mapping_count()
    before, _inserted, after = _parse_mapping_seed_counts(
        sqlcmd(qms_detail_mapping_sql(company_id()))
    )
    if after < expected:
        raise RuntimeError(
            f"EntityMapping seed: {after}/{expected} Tests/Results maps present"
        )
    return 1 if before < expected else 0


def _recycle_app_pool() -> None:
    inst = instance()
    if not inst.ssh:
        return
    ssh_run("Restart-WebAppPool -Name AcumaticaERP")
    wait_published(timeout=120.0)


def qms_setup_insert_sql() -> str:
    """INSERT UsrQMSSetup (QORD QNCR) per Company row when missing."""
    nil = "00000000-0000-0000-0000-000000000000"
    return (
        f"INSERT INTO {DB_NAME}.dbo.UsrQMSSetup ("
        "CompanyID, InspectionOrderNumberingID, NCRNumberingID, "
        "CreatedByID, CreatedByScreenID, CreatedDateTime, "
        "LastModifiedByID, LastModifiedByScreenID, LastModifiedDateTime"
        f") SELECT c.CompanyID, N'{QORD}', N'{QNCR}', "
        f"'{nil}', 'QM101000', GETDATE(), "
        f"'{nil}', 'QM101000', GETDATE() "
        f"FROM {DB_NAME}.dbo.Company c "
        f"WHERE NOT EXISTS (SELECT 1 FROM {DB_NAME}.dbo.UsrQMSSetup t "
        "WHERE t.CompanyID = c.CompanyID)"
    )


def _ensure_qms_setup_rows() -> None:
    """Insert UsrQMSSetup (QORD QNCR) per company when missing."""
    sqlcmd(qms_setup_insert_sql())


def quality_queue_seed_sql(cid: int) -> str:
    """Replace QM401000 GIDesign children (26.101 GI XML upgrades fail)."""
    nil = "00000000-0000-0000-0000-000000000000"
    did = QM401000_DESIGN_ID
    db = DB_NAME
    return (
        f"DECLARE @cid int = {cid}; "
        f"DECLARE @did uniqueidentifier = '{did}'; "
        "DECLARE @mask varbinary(32); "
        f"SELECT TOP 1 @mask = CompanyMask FROM {db}.dbo.GIDesign WHERE CompanyID = @cid; "
        "IF @mask IS NULL SET @mask = 0xAAAAAAAA; "
        f"IF NOT EXISTS (SELECT 1 FROM {db}.dbo.GIDesign WHERE CompanyID = @cid AND DesignID = @did) "
        f"INSERT INTO {db}.dbo.GIDesign ("
        "CompanyID, DesignID, Name, NewRecordCreationEnabled, MassDeleteEnabled, "
        "AutoConfirmDelete, MassRecordsUpdateEnabled, MassActionsOnRecordsEnabled, "
        "ExposeViaOData, ExposeViaMobile, ShowDeletedRecords, ShowArchivedRecords, "
        "DisableCountsAndTotals, CreatedByID, CreatedDateTime, CreatedByScreenID, "
        "LastModifiedByID, LastModifiedDateTime, LastModifiedByScreenID, NoteID, CompanyMask"
        ") VALUES ("
        f"@cid, @did, N'Quality Queue', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "
        f"'{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        "BEGIN "
        f"DELETE FROM {db}.dbo.GINavigationParameter WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GINavigationScreen WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GISort WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GIGroupBy WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GIWhere WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GIResult WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GIOn WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GIRelation WHERE CompanyID = @cid AND DesignID = @did; "
        f"DELETE FROM {db}.dbo.GITable WHERE CompanyID = @cid AND DesignID = @did; "
        f"INSERT INTO {db}.dbo.GITable ("
        "CompanyID, DesignID, Alias, Name, Type, CreatedByID, CreatedDateTime, "
        "CreatedByScreenID, LastModifiedByID, LastModifiedDateTime, LastModifiedByScreenID, "
        "NoteID, CompanyMask) VALUES "
        f"(@cid, @did, N'Order', N'Lab5.QMS.QMSInspectionOrder', 0, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, N'Lot', N'PX.Objects.IN.INLotSerialStatusByCostCenter', 0, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, N'NCR', N'Lab5.QMS.QMSNonConformance', 0, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, N'Item', N'PX.Objects.IN.InventoryItem', 0, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, N'Vendor', N'PX.Objects.AP.Vendor', 0, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        f"INSERT INTO {db}.dbo.GIRelation ("
        "CompanyID, DesignID, LineNbr, ParentTable, ChildTable, IsActive, JoinType, "
        "CreatedByID, CreatedDateTime, CreatedByScreenID, LastModifiedByID, "
        "LastModifiedDateTime, LastModifiedByScreenID, NoteID, CompanyMask) VALUES "
        f"(@cid, @did, 1, N'Order', N'Lot', 1, 'L', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 2, N'Order', N'NCR', 1, 'L', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 3, N'Order', N'Item', 1, 'L', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 4, N'Order', N'Vendor', 1, 'L', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        f"INSERT INTO {db}.dbo.GIOn ("
        "CompanyID, DesignID, RelationNbr, LineNbr, ParentField, Condition, ChildField, Operation, "
        "CreatedByID, CreatedDateTime, CreatedByScreenID, LastModifiedByID, "
        "LastModifiedDateTime, LastModifiedByScreenID, NoteID, CompanyMask) VALUES "
        f"(@cid, @did, 1, 1, N'inventoryID', 'E', N'inventoryID', 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 1, 2, N'lotSerialNbr', 'E', N'lotSerialNbr', 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 2, 1, N'inspectionOrderNbr', 'E', N'inspectionOrderNbr', 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 3, 1, N'inventoryID', 'E', N'inventoryID', 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 4, 1, N'vendorID', 'E', N'bAccountID', 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        f"INSERT INTO {db}.dbo.GIResult ("
        "CompanyID, DesignID, LineNbr, SortOrder, IsActive, ObjectName, Field, Caption, "
        "IsVisible, DefaultNav, NavigationNbr, QuickFilter, FastFilter, AggregateFunction, RowID, "
        "CreatedByID, CreatedDateTime, CreatedByScreenID, LastModifiedByID, "
        "LastModifiedDateTime, LastModifiedByScreenID, NoteID, CompanyMask) VALUES "
        f"(@cid, @did, 1, 1, 1, N'Item', N'inventoryCD', N'Inventory', 1, 0, NULL, 0, 1, NULL, NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 2, 2, 1, N'Order', N'lotSerialNbr', N'Lot', 1, 0, NULL, 0, 1, NULL, NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 3, 3, 1, N'Order', N'receiptNbr', N'Receipt', 1, 0, NULL, 0, 1, NULL, NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 4, 4, 1, N'Vendor', N'acctCD', N'Vendor', 1, 0, NULL, 0, 1, NULL, NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 5, 5, 1, N'Order', N'planID', N'Plan', 1, 0, NULL, 0, 1, NULL, NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 6, 6, 1, N'Lot', N'usrQMSLotStatus', N'Lot Status', 1, 0, NULL, 0, 1, N'MAX', NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 7, 7, 1, N'Order', N'inspectionOrderNbr', N'Order Nbr', 1, 1, 1, 1, 1, NULL, NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 8, 8, 1, N'Order', N'status', N'Order Status', 1, 0, NULL, 0, 0, NULL, NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 9, 9, 1, N'NCR', N'nCRNbr', N'NCR Nbr', 1, 1, 2, 1, 1, N'MAX', NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 10, 10, 1, N'NCR', N'status', N'NCR Status', 1, 0, NULL, 0, 0, N'MAX', NEWID(), '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        f"INSERT INTO {db}.dbo.GIWhere ("
        "CompanyID, DesignID, LineNbr, IsActive, OpenBrackets, DataFieldName, Condition, "
        "IsExpression, Value1, CloseBrackets, Operation, CreatedByID, CreatedDateTime, "
        "CreatedByScreenID, LastModifiedByID, LastModifiedDateTime, LastModifiedByScreenID, "
        "NoteID, CompanyMask) VALUES "
        f"(@cid, @did, 1, 1, N'(', N'Lot.usrQMSLotStatus', 'E', 0, N'QC Hold', N')', 'O', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 2, 1, N'(', N'Order.status', 'NE', 0, N'C', N')', 'O', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 3, 1, N'(', N'NCR.nCRNbr', 'NN', 0, NULL, NULL, 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask), "
        f"(@cid, @did, 4, 1, NULL, N'NCR.status', 'NE', 0, N'C', N')', 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        f"INSERT INTO {db}.dbo.GISort ("
        "CompanyID, DesignID, LineNbr, IsActive, DataFieldName, SortOrder, "
        "CreatedByID, CreatedDateTime, CreatedByScreenID, LastModifiedByID, "
        "LastModifiedDateTime, LastModifiedByScreenID, NoteID, CompanyMask) VALUES "
        f"(@cid, @did, 1, 1, N'Order.inspectionOrderNbr', 'A', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        f"INSERT INTO {db}.dbo.GIGroupBy ("
        "CompanyID, DesignID, LineNbr, IsActive, DataFieldName, "
        "CreatedByID, CreatedDateTime, CreatedByScreenID, LastModifiedByID, "
        "LastModifiedDateTime, LastModifiedByScreenID, NoteID, CompanyMask) VALUES "
        f"(@cid, @did, 1, 1, N'Order.inspectionOrderNbr', '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', NEWID(), @mask); "
        f"INSERT INTO {db}.dbo.GINavigationScreen ("
        "CompanyID, DesignID, Link, LineNbr, SortOrder, WindowMode, IsActive, NoteID, CompanyMask, "
        "CreatedByID, CreatedDateTime, CreatedByScreenID, LastModifiedByID, "
        "LastModifiedDateTime, LastModifiedByScreenID) VALUES "
        f"(@cid, @did, N'QM301000', 1, 1, N'L', 1, NEWID(), @mask, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000'), "
        f"(@cid, @did, N'QM302000', 2, 2, N'L', 1, NEWID(), @mask, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000'); "
        f"INSERT INTO {db}.dbo.GINavigationParameter ("
        "CompanyID, DesignID, NavigationScreenLineNbr, LineNbr, FieldName, ParameterName, "
        "IsExpression, CreatedByID, CreatedDateTime, CreatedByScreenID, LastModifiedByID, "
        "LastModifiedDateTime, LastModifiedByScreenID, CompanyMask) VALUES "
        f"(@cid, @did, 1, 1, N'InspectionOrderNbr', N'Order.inspectionOrderNbr', 0, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', @mask), "
        f"(@cid, @did, 2, 1, N'NCRNbr', N'NCR.nCRNbr', 0, '{nil}', GETDATE(), 'QM401000', '{nil}', GETDATE(), 'QM401000', @mask); "
        "END"
    )


def _ensure_quality_queue_gi() -> None:
    sqlcmd(quality_queue_seed_sql(company_id()))


def _ensure_qm_aspx_pages() -> None:
    """Copy stub aspx onto the site. REST QMS entities 500 if Pages/QM/*.aspx is missing."""
    inst = instance()
    if not inst.ssh:
        return
    root = Path(__file__).resolve().parents[1]
    remote_dir = ACU_INSTANCE_PATH.replace("\\", "/") + "/Pages/QM"
    ssh_run(
        "New-Item -ItemType Directory -Force -Path '"
        + ACU_INSTANCE_PATH
        + r"\Pages\QM' | Out-Null"
    )
    for screen in ("QM101000", "QM201000", "QM301000", "QM302000"):
        for suffix in (".aspx", ".aspx.cs"):
            local = root / "Pages_QM" / f"{screen}{suffix}"
            remote = f"{inst.ssh}:{remote_dir}/{screen}{suffix}"
            result = subprocess.run(
                ["scp", "-o", "BatchMode=yes", str(local), remote],
                capture_output=True,
                text=True,
                check=False,
                timeout=SSH_TIMEOUT,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"scp {local.name} failed ({result.returncode}):\n"
                    f"{result.stdout}\n{result.stderr}"
                )


def seed_qm_rights(session: AcumaticaClient) -> None:
    """Post-publish Role Quality Manager + QM RolesInGraph + UsrQMSSetup. No ACU_USER attach."""
    with progress("seed Role", QUALITY_MANAGER_ROLE):
        boot = bootstrap_endpoint(session)
        session.put(
            "Role",
            {"Rolename": QUALITY_MANAGER_ROLE, "Descr": "QC Hold to Released"},
            endpoint=boot,
        )
        _ensure_quality_manager_role_row()
    with progress("seed RolesInGraph", ",".join(QM_SCREENS)):
        _ensure_qm_roles_in_graph()
    with progress("seed EntityMapping", "Tests,Results"):
        if _ensure_qms_detail_mappings():
            _recycle_app_pool()
    with progress("seed UsrQMSSetup", f"{QORD},{QNCR}"):
        _ensure_qms_setup_rows()
    with progress("seed Quality Queue GI", "QM401000"):
        _ensure_quality_queue_gi()
    with progress("seed Pages/QM aspx", "REST"):
        _ensure_qm_aspx_pages()
