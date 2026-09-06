"""CustomizationApi publish + post-publish QM Role seed (T14 / V10 / V8).

Zip never carries Role / UsersInRoles / RolesInGraph (V8 / I.pkg).
`ACU_USER` Quality Manager attach stays e2e-only (V10).
Never prints ACU_PASSWORD.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from acumatica_cli.client import AcumaticaClient
from acumatica_cli.config import DB_NAME, Instance, load_instance
from acumatica_cli.tenant import TenantManager

from lab5_qms import pack

PACKAGE_NAME = "Lab5.QMS"
QMS_ENDPOINT = "QMS/22.200.001"
QMS_VERSION = "22.200.001"

QM_SCREENS = ("QM101000", "QM201000", "QM301000", "QM302000")
QUALITY_MANAGER_ROLE = "Quality Manager"
QM_RIGHTS_ROLES = ("Administrator", QUALITY_MANAGER_ROLE)
ROLES_IN_GRAPH_COMPANY_ID = 1
ROLES_IN_GRAPH_APPLICATION = "/"
ACCESSRIGHTS_DELETE = 4

HTTP_TIMEOUT = 30.0
SSH_TIMEOUT = 30.0


def instance() -> Instance:
    return load_instance()


@contextmanager
def client(timeout: float = HTTP_TIMEOUT) -> Iterator[AcumaticaClient]:
    with AcumaticaClient(instance(), timeout=timeout) as session:
        yield session


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


def zip_digest(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        digest = hashlib.sha256()
        digest.update(zf.read("project.xml"))
        dll_name = "Bin/" + pack.ASSEMBLY_DLL
        if dll_name in zf.namelist():
            digest.update(zf.read(dll_name))
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


def drain_publish(session: AcumaticaClient, timeout: float = 120.0) -> None:
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
        except (RuntimeError, httpx.TransportError, httpx.HTTPError):
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
        drain_publish(session)
        names = session.customization_published()
        same = (
            PACKAGE_NAME in names
            and published_description(session) == description
            and ("QMS", QMS_VERSION) in session.list_endpoints()
        )
        if same:
            return "already published"
        session.customization_import(
            PACKAGE_NAME, zip_bytes, description=description
        )
        publish_begin(session, [PACKAGE_NAME])
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

    wait_published(timeout=120.0)
    return "published"


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


def seed_qm_rights(session: AcumaticaClient) -> None:
    """Post-publish Role Quality Manager + QM RolesInGraph. No ACU_USER attach."""
    boot = bootstrap_endpoint(session)
    session.put(
        "Role",
        {"Rolename": QUALITY_MANAGER_ROLE, "Descr": "QC Hold to Released"},
        endpoint=boot,
    )
    _ensure_quality_manager_role_row()
    _ensure_qm_roles_in_graph()
