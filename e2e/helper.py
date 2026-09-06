"""Live-tenant helpers for Lab5.QMS e2e.

Uses `uv run` (`import acumatica_cli`) so `.env` walk-up matches
`uv run acu config check`. Never call `acu check` (destructive rebuild).
Never print ACU_PASSWORD.
"""

from __future__ import annotations

import faulthandler
import hashlib
import io
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx

from acumatica_cli.client import AcumaticaClient, unwrap, wrap
from acumatica_cli.config import DB_NAME, Instance, load_instance
from acumatica_cli.tenant import TenantManager

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pack  # noqa: E402

PACKAGE_NAME = "Lab5.QMS"
QMS_ENDPOINT = "QMS/22.200.001"
QMS_VERSION = "22.200.001"

USR_QMS_TABLES = (
    "UsrQMSInspectionPlan",
    "UsrQMSInspectionPlanTest",
    "UsrQMSInspectionOrder",
    "UsrQMSInspectionOrderResult",
    "UsrQMSNonConformance",
    "UsrQMSSetup",
)
USR_ITEM_COLUMNS = (
    "UsrQMSInspectionRequired",
    "UsrQMSInspectionPlanID",
    "UsrMinShelfLifeDays",
)
QM_SCREENS = ("QM101000", "QM201000", "QM301000", "QM302000")
QUALITY_MANAGER_ROLE = "Quality Manager"
QM_RIGHTS_ROLES = ("Administrator", QUALITY_MANAGER_ROLE)
ROLES_IN_GRAPH_COMPANY_ID = 1
ROLES_IN_GRAPH_APPLICATION = "/"
ACCESSRIGHTS_DELETE = 4

PLAN_ID = "E2EQPLAN-ECH4"
ITEM_CD = "RAW-ECH-EXT4"
VENDOR_CD = "VEND-NORTH-BIO"
PASS_ORDER = "E2EPASSC0A001"
FAIL_ORDER = "E2EFAILC0A001"
NCR_NBR = "E2ENCR00000001"

OVERALL_PASS = "V"
OVERALL_FAIL = "F"
STATUS_COMPLETED = "C"
LINE_PASS = "P"
LINE_FAIL = "F"

MIN_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)

_published: bool | None = None
_publish_error: BaseException | None = None

# Per-request HTTP bound. Publish polling uses this plus a loop deadline
# (ensure_published timeout=600); do not raise the default back to 300s —
# a stuck GET then looks like a hung `gmake check`.
HTTP_TIMEOUT = 30.0
ACU_TIMEOUT = 60.0
INVOKE_TIMEOUT = 60.0
SSH_TIMEOUT = 30.0


def _arm_e2e_timeout() -> None:
    """Kill a stuck e2e process. `E2E_TIMEOUT` seconds; 0 disables."""
    raw = os.environ.get("E2E_TIMEOUT")
    if not raw:
        return
    seconds = float(raw)
    if seconds <= 0:
        return
    faulthandler.dump_traceback_later(seconds, exit=True)


_arm_e2e_timeout()


def instance() -> Instance:
    return load_instance()


@contextmanager
def client(timeout: float = HTTP_TIMEOUT) -> Iterator[AcumaticaClient]:
    with AcumaticaClient(instance(), timeout=timeout) as session:
        yield session


def run_acu(
    *args: str, timeout: float = ACU_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """Run the installed `acu` binary from the repo root (`.env` walk-up)."""
    try:
        return subprocess.run(
            ["acu", *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"acu {' '.join(args)} timed out after {timeout:.0f}s"
        ) from exc


def bootstrap_endpoint(session: AcumaticaClient) -> str:
    versions = [ver for name, ver in session.list_endpoints() if name == "Bootstrap"]
    if not versions:
        raise RuntimeError("Bootstrap endpoint not published on this tenant")
    return f"Bootstrap/{max(versions)}"


def company_id() -> int:
    inst = instance()
    mgr = TenantManager(inst)
    for tenant in mgr.list():
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


def _zip_digest(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        digest = hashlib.sha256()
        digest.update(zf.read("project.xml"))
        dll_name = "Bin/" + pack.ASSEMBLY_DLL
        if dll_name in zf.namelist():
            digest.update(zf.read(dll_name))
        return digest.hexdigest()


def _published_description(session: AcumaticaClient) -> str | None:
    content = session.customization_project_content(PACKAGE_NAME)
    if content is None:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            root = ET.fromstring(zf.read("project.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
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


def _drain_publish(session: AcumaticaClient, timeout: float = 120.0) -> None:
    """Finish or fail the in-flight publish before starting another."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = session.customization_publish_end()
        except (httpx.TransportError, RuntimeError):
            return
        if status.get("isCompleted") or status.get("isFailed"):
            return
        time.sleep(2.0)


def _publish_begin(session: AcumaticaClient, names: list[str]) -> None:
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


def _wait_published(timeout: float = 600.0, poll: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with client() as session:
                if ("QMS", QMS_VERSION) in session.list_endpoints():
                    return
        except (RuntimeError, httpx.TransportError, httpx.HTTPError):
            pass
        time.sleep(poll)
    raise RuntimeError(
        f"{QMS_ENDPOINT} did not appear on GET /entity within {timeout:.0f}s"
    )


def ensure_published(*, timeout: float = 600.0) -> str:
    """Import + publish Lab5.QMS if the live package digest differs.

    Merges with already-published projects (AcuBootstrap must stay).
    """
    global _published, _publish_error
    if _published:
        return "already published"
    if _publish_error is not None:
        raise _publish_error

    zip_bytes = pack.package_zip(ROOT)
    description = (
        "QMS customization 22.200.001; assembly Lab5.QMS.dll; "
        f"zip Lab5_QMS_Customization.zip [sha256:{_zip_digest(zip_bytes)}]"
    )

    try:
        status = _import_and_publish(zip_bytes, description, timeout)
        with client() as session:
            ensure_qm_rights(session)
        return status
    except BaseException as exc:
        _publish_error = exc
        raise


def _import_and_publish(zip_bytes: bytes, description: str, timeout: float) -> str:
    global _published
    with client() as session:
        _drain_publish(session)
        names = session.customization_published()
        same = (
            PACKAGE_NAME in names
            and _published_description(session) == description
            and ("QMS", QMS_VERSION) in session.list_endpoints()
        )
        if same:
            _published = True
            return "already published"
        session.customization_import(
            PACKAGE_NAME, zip_bytes, description=description
        )
        _publish_begin(session, [PACKAGE_NAME])
        deadline = time.monotonic() + timeout
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

    _wait_published(timeout=120.0)
    _published = True
    return "published"


def put_file(session: AcumaticaClient, order_nbr: str, file_name: str, body: bytes) -> None:
    path = f"/entity/{QMS_ENDPOINT}/InspectionOrder/{order_nbr}/files/{file_name}"
    session._checked(
        session._http.put(
            path,
            content=body,
            headers={"Content-Type": "application/octet-stream"},
        )
    )


def qms_get(
    session: AcumaticaClient,
    entity: str,
    keys: list[str] | None = None,
    params: dict[str, str] | None = None,
) -> Any:
    if keys is None:
        return session.get_list(entity, params=params, endpoint=QMS_ENDPOINT)
    return session.get_record(entity, keys, endpoint=QMS_ENDPOINT, params=params)


def qms_put(session: AcumaticaClient, entity: str, record: dict[str, Any]) -> dict[str, Any]:
    return unwrap(session.put(entity, record, endpoint=QMS_ENDPOINT))


def qms_invoke(
    session: AcumaticaClient,
    action: str,
    record: dict[str, Any],
    timeout: float = INVOKE_TIMEOUT,
) -> None:
    """POST InspectionOrder action; bound the 202 status poll.

    `AcumaticaClient.invoke` polls Location while status is 202 with no
    deadline — a stuck EvaluateResults/ReleaseLotDecision hangs `gmake check`.
    """
    body: dict[str, Any] = {"entity": wrap(record)}
    r = session._checked(
        session._http.post(
            f"{session._url('InspectionOrder', QMS_ENDPOINT)}/{action}",
            json=body,
        )
    )
    deadline = time.monotonic() + timeout
    while r.status_code == 202:
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"InspectionOrder {action} did not complete within {timeout:.0f}s"
            )
        status_url = r.request.url.join(r.headers.get("Location", ""))
        time.sleep(session.poll_interval)
        r = session._checked(session._http.get(status_url))


def roles_in_graph_rows() -> tuple[tuple[str, str], ...]:
    """(Rolename, ScreenID) pairs for V10 RolesInGraph Delete seed."""
    return tuple(
        (role, screen) for role in QM_RIGHTS_ROLES for screen in QM_SCREENS
    )


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


def ensure_qm_rights(session: AcumaticaClient) -> None:
    """Post-publish Role Quality Manager + QM RolesInGraph + ACU_USER attach."""
    boot = bootstrap_endpoint(session)
    session.put(
        "Role",
        {"Rolename": QUALITY_MANAGER_ROLE, "Descr": "QC Hold to Released"},
        endpoint=boot,
    )
    _ensure_quality_manager_role_row()
    _ensure_acu_user_quality_manager()
    _ensure_qm_roles_in_graph()


def ensure_numbering_and_role(session: AcumaticaClient) -> None:
    ensure_qm_rights(session)
    _ensure_numbering_rows()
    _ensure_setup_row()


def _ensure_qm_roles_in_graph() -> None:
    sqlcmd(roles_in_graph_merge_sql(roles_in_graph_company_ids()))


def _sql_nvarchar(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def _ensure_numbering_rows() -> None:
    """Insert QORD/QNCR on CompanyID 1 (shared Numbering table)."""
    nil = "00000000-0000-0000-0000-000000000000"
    for numbering_id, descr in (("QORD", "QMS Inspection Order"), ("QNCR", "QMS NCR")):
        sqlcmd(
            "IF NOT EXISTS (SELECT 1 FROM "
            f"{DB_NAME}.dbo.Numbering WHERE CompanyID = 1 "
            f"AND NumberingID = N'{numbering_id}') "
            f"INSERT INTO {DB_NAME}.dbo.Numbering ("
            "CompanyID, NumberingID, Descr, UserNumbering, NewSymbol, NoteID, "
            "CreatedByID, CreatedByScreenID, CreatedDateTime, "
            "LastModifiedByID, LastModifiedByScreenID, LastModifiedDateTime"
            ") VALUES ("
            f"1, N'{numbering_id}', N'{descr}', 1, N'{numbering_id}', NEWID(), "
            f"'{nil}', 'QM101000', GETDATE(), '{nil}', 'QM101000', GETDATE()); "
            "IF NOT EXISTS (SELECT 1 FROM "
            f"{DB_NAME}.dbo.NumberingSequence WHERE CompanyID = 1 "
            f"AND NumberingID = N'{numbering_id}') "
            f"INSERT INTO {DB_NAME}.dbo.NumberingSequence ("
            "CompanyID, NumberingID, StartNbr, EndNbr, StartDate, LastNbr, "
            "WarnNbr, NbrStep, CreatedByID, CreatedByScreenID, CreatedDateTime, "
            "LastModifiedByID, LastModifiedByScreenID, LastModifiedDateTime"
            ") VALUES ("
            f"1, N'{numbering_id}', N'000000', N'999999', '19000101', "
            f"N'000000', N'999990', 1, '{nil}', 'QM101000', GETDATE(), "
            f"'{nil}', 'QM101000', GETDATE())"
        )


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


def _ensure_acu_user_quality_manager() -> None:
    """Attach Quality Manager to ACU_USER on CompanyID 1 and the tenant."""
    user = _sql_nvarchar(instance().user)
    role = _sql_nvarchar(QUALITY_MANAGER_ROLE)
    companies = ", ".join(f"({cid})" for cid in roles_in_graph_company_ids())
    sqlcmd(
        f"INSERT INTO {DB_NAME}.dbo.UsersInRoles ("
        "CompanyID, Username, Rolename, ApplicationName, CompanyMask, "
        "CreatedByID, CreatedByScreenID, CreatedDateTime, "
        "LastModifiedByID, LastModifiedByScreenID, LastModifiedDateTime"
        ") SELECT c.CompanyID, "
        f"{user}, {role}, u.ApplicationName, u.CompanyMask, "
        "u.CreatedByID, 'QM101000', GETDATE(), "
        "u.LastModifiedByID, 'QM101000', GETDATE() "
        f"FROM (VALUES {companies}) AS c(CompanyID) "
        f"INNER JOIN {DB_NAME}.dbo.UsersInRoles u "
        "ON u.CompanyID = c.CompanyID AND u.Username = "
        f"{user} AND u.Rolename = N'Administrator' "
        "AND u.ApplicationName = "
        f"N'{ROLES_IN_GRAPH_APPLICATION}' "
        f"WHERE NOT EXISTS (SELECT 1 FROM {DB_NAME}.dbo.UsersInRoles t "
        "WHERE t.CompanyID = c.CompanyID AND t.Username = "
        f"{user} AND t.Rolename = {role} "
        "AND t.ApplicationName = u.ApplicationName)"
    )


def _ensure_setup_row() -> None:
    cid = company_id()
    sqlcmd(
        "IF NOT EXISTS (SELECT 1 FROM "
        f"{DB_NAME}.dbo.UsrQMSSetup WHERE CompanyID = {cid}) "
        f"INSERT INTO {DB_NAME}.dbo.UsrQMSSetup ("
        "CompanyID, InspectionOrderNumberingID, NCRNumberingID, "
        "CreatedByID, CreatedByScreenID, CreatedDateTime, "
        "LastModifiedByID, LastModifiedByScreenID, LastModifiedDateTime"
        ") VALUES ("
        f"{cid}, N'QORD', N'QNCR', "
        "'00000000-0000-0000-0000-000000000000', 'QM101000', GETDATE(), "
        "'00000000-0000-0000-0000-000000000000', 'QM101000', GETDATE())"
    )
