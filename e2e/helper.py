"""Live-tenant helpers for Lab5.QMS e2e.

PATH `acu` (released `uv tool install`) resolves `.env` via walk-up.
acu is never launched through uv. Never call `acu check` (destructive rebuild).
Never print ACU_PASSWORD.
"""

from __future__ import annotations

import faulthandler
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from lab5_qms import pack
from lab5_qms.acu import (  # noqa: F401
    AcumaticaClient,
    DB_NAME,
    HTTP_TIMEOUT,
    run_acu as _run_acu,
    unwrap,
    wrap,
)
from lab5_qms.publish import (  # noqa: F401
    ACCESSRIGHTS_DELETE,
    PACKAGE_NAME,
    QM_RIGHTS_ROLES,
    QM_SCREENS,
    QMS_ENDPOINT,
    QMS_VERSION,
    QUALITY_MANAGER_ROLE,
    ROLES_IN_GRAPH_APPLICATION,
    ROLES_IN_GRAPH_COMPANY_ID,
    SSH_TIMEOUT,
    _ensure_qms_setup_rows,
    bootstrap_endpoint,
    client,
    company_id,
    instance,
    publish_package,
    roles_in_graph_company_ids,
    roles_in_graph_merge_sql,
    roles_in_graph_rows,
    seed_qm_rights,
    sql_lines,
    sqlcmd,
)

ROOT = Path(__file__).resolve().parents[1]

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

# Per-request HTTP bound lives in lab5_qms.acu (HTTP_TIMEOUT = 30.0).
# Publish polling uses that plus a loop deadline (ensure_published
# timeout=600); do not raise the default back to 300s — a stuck GET then
# looks like a hung `gmake check`.
ACU_TIMEOUT = 60.0
INVOKE_TIMEOUT = 60.0


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


def run_acu(
    *args: str, timeout: float = ACU_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """Run PATH `acu` from the repo root (`.env` walk-up). Never through uv."""
    return _run_acu(*args, timeout=timeout, cwd=ROOT)


def ensure_published(*, timeout: float = 600.0) -> str:
    """Import + publish Lab5.QMS if the live package digest differs.

    Merges with already-published projects (AcuBootstrap must stay).
    """
    global _published, _publish_error
    if _published:
        return "already published"
    if _publish_error is not None:
        raise _publish_error

    zip_bytes = pack.package_zip(ROOT, ensure_dll=True)
    try:
        status = publish_package(zip_bytes, timeout=timeout)
        _published = True
        with client() as session:
            ensure_qm_rights(session)
        return status
    except BaseException as exc:
        _publish_error = exc
        raise


def put_file(
    session: AcumaticaClient, order_nbr: str, file_name: str, body: bytes
) -> None:
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


def qms_put(
    session: AcumaticaClient, entity: str, record: dict[str, Any]
) -> dict[str, Any]:
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


_qm_roles_recycled = False


def ensure_qm_rights(session: AcumaticaClient) -> None:
    """Post-publish Role seed plus e2e-only ACU_USER Quality Manager attach."""
    seed_qm_rights(session)
    _ensure_acu_user_quality_manager()
    global _qm_roles_recycled
    if not _qm_roles_recycled:
        from lab5_qms.publish import _recycle_app_pool

        _recycle_app_pool()
        _qm_roles_recycled = True


def ensure_numbering_and_role(session: AcumaticaClient) -> None:
    ensure_qm_rights(session)
    _ensure_numbering_rows()
    _ensure_setup_row()


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
    _ensure_qms_setup_rows()
