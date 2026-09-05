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
        return hashlib.sha256(zf.read("project.xml")).hexdigest()


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
        return _import_and_publish(zip_bytes, description, timeout)
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


def ensure_numbering_and_role(session: AcumaticaClient) -> None:
    boot = bootstrap_endpoint(session)
    _ensure_numbering_rows()
    session.put(
        "Role",
        {"Rolename": "Quality Manager", "Descr": "QC Hold to Released"},
        endpoint=boot,
    )
    _ensure_admin_quality_manager(session, boot)
    _ensure_setup_row()


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


def _ensure_admin_quality_manager(session: AcumaticaClient, boot: str) -> None:
    user = session.get_record(
        "User", [instance().user], endpoint=boot, params={"$expand": "Roles"}
    )
    if user is None:
        return
    body = unwrap(user)
    roles = list(body.get("Roles") or [])
    if any(
        str(row.get("Rolename", "")).casefold() == "quality manager"
        and row.get("Selected")
        for row in roles
        if isinstance(row, dict)
    ):
        return
    roles.append({"Rolename": "Quality Manager", "Selected": True})
    session.put(
        "User",
        {"Username": instance().user, "Roles": roles},
        endpoint=boot,
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
