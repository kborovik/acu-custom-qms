#!/usr/bin/env -S uv run
"""T28 / V15: KitAssembly PUT/Release with a QC Hold component lot must fail."""

from __future__ import annotations

import time
import unittest

from e2e.helper import (
    DB_NAME,
    ITEM_CD,
    VENDOR_CD,
    client,
    company_id,
    ensure_numbering_and_role,
    ensure_published,
    instance,
    sql_lines,
    sqlcmd,
    unwrap,
    wrap,
)
from lab5_qms.acu import AcumaticaClient
from e2e.test_functional import GITOPS_PLANS, _seed_ready
from e2e.test_qms_setup import GITOPS_QMS_SETUP
from e2e.test_stock_item_qms import GITOPS_STOCK_ITEMS

KIT_CD = "FG-IMMUNE-DEFENSE-60C"
COMPONENT_CD = ITEM_CD  # RAW-ECH-EXT4
WAREHOUSE = "WH-MISS-01"
LOCATION = "MAIN"
KIT_TYPE = "Assembly"
QC_HOLD = "QC Hold"
QUARANTINE = "Quarantine"
RELEASED = "Released"
GATE_TOKENS = (QC_HOLD, QUARANTINE, RELEASED)


def _invoke_default(session, entity: str, action: str, record: dict, timeout: float = 120.0):
    r = session._checked(
        session._http.post(
            f"{session._url(entity)}/{action}",
            json={"entity": wrap(record)},
        )
    )
    deadline = time.monotonic() + timeout
    while r.status_code == 202:
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"{entity} {action} did not complete within {timeout:.0f}s"
            )
        status_url = r.request.url.join(r.headers.get("Location", ""))
        time.sleep(session.poll_interval)
        r = session._checked(session._http.get(status_url))
    return r


def _sql_lot_status(item_cd: str, lot: str) -> str | None:
    if not instance().ssh:
        return None
    rows = sql_lines(
        "SELECT TOP 1 RTRIM(ISNULL(l.UsrQMSLotStatus, N'')) "
        f"FROM {DB_NAME}.dbo.INLotSerialStatusByCostCenter l "
        f"JOIN {DB_NAME}.dbo.InventoryItem i "
        "ON i.CompanyID = l.CompanyID AND i.InventoryID = l.InventoryID "
        f"WHERE l.CompanyID = {company_id()} "
        f"AND RTRIM(i.InventoryCD) = N'{item_cd}' "
        f"AND RTRIM(l.LotSerialNbr) = N'{lot}'"
    )
    if not rows:
        return None
    return rows[0]


def _force_qc_hold(item_cd: str, lot: str) -> None:
    if not instance().ssh:
        return
    sqlcmd(
        f"UPDATE {DB_NAME}.dbo.INLotSerialStatusByCostCenter "
        "SET UsrQMSLotStatus = N'QC Hold' "
        f"FROM {DB_NAME}.dbo.INLotSerialStatusByCostCenter l "
        f"JOIN {DB_NAME}.dbo.InventoryItem i "
        "ON i.CompanyID = l.CompanyID AND i.InventoryID = l.InventoryID "
        f"WHERE l.CompanyID = {company_id()} "
        f"AND RTRIM(i.InventoryCD) = N'{item_cd}' "
        f"AND RTRIM(l.LotSerialNbr) = N'{lot}'"
    )


def _error_text(payload: object) -> str:
    parts: list[str] = []
    if isinstance(payload, BaseException):
        parts.append(str(payload))
        payload = getattr(payload, "body", None) or payload
    cur: object = payload
    while isinstance(cur, dict):
        for key in ("exceptionMessage", "message", "error"):
            val = cur.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        cur = cur.get("innerException")
    if isinstance(payload, dict):
        parts.extend(AcumaticaClient._field_errors(payload))
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            out.append(part)
    return " ".join(out)


def _gate_message(text: str) -> bool:
    return all(token in text for token in GATE_TOKENS)


class TestKitAssemblyRefusesQcHoldLotV15(unittest.TestCase):
    """V15: allocating a QC Hold lot on Kit Assembly must fail."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            reason = _seed_ready(session)
            if reason:
                raise unittest.SkipTest(reason)
            kit = session.get_record("StockItem", [KIT_CD])
            if kit is None:
                raise unittest.SkipTest(
                    f"StockItem {KIT_CD} missing — seed tenant from acu-gitops-qms"
                )
            item = unwrap(session.get_record("StockItem", [COMPONENT_CD]) or {})
            lot_class = (
                item.get("LotSerialClass") or item.get("LotSerClass") or ""
            ).strip()
            if not lot_class:
                raise unittest.SkipTest(
                    f"{COMPONENT_CD} has no LotSerialClass — kit lot e2e needs "
                    "lot-tracked items from acu-gitops-qms"
                )
            cls.warehouse = (
                item.get("DefaultWarehouseID")
                or item.get("DefaultWarehouse")
                or WAREHOUSE
            ).strip() or WAREHOUSE
            ensure_numbering_and_role(session)
            session.put("QMSSetup", GITOPS_QMS_SETUP, endpoint="QMS/22.200.001")
            if GITOPS_PLANS:
                session.put(
                    "InspectionPlan", GITOPS_PLANS[0], endpoint="QMS/22.200.001"
                )
            session.put("StockItem", dict(GITOPS_STOCK_ITEMS[0]), endpoint="QMS/22.200.001")

    def test_put_or_release_kit_with_qc_hold_lot_fails(self) -> None:
        stamp = time.strftime("%H%M%S")
        lot = f"E2EKIT{stamp}"
        with client() as session:
            po = unwrap(
                session.put(
                    "PurchaseOrder",
                    {
                        "VendorID": VENDOR_CD,
                        "Hold": False,
                        "Details": [
                            {
                                "InventoryID": COMPONENT_CD,
                                "OrderQty": 1,
                                "UnitCost": 1.0,
                            }
                        ],
                    },
                )
            )
            order_nbr = (po.get("OrderNbr") or "").strip()
            self.assertTrue(order_nbr, "PurchaseOrder PUT returned no OrderNbr")
            details = po.get("Details") or []
            if not details:
                po = unwrap(
                    session.get_record(
                        "PurchaseOrder",
                        ["Normal", order_nbr],
                        params={"$expand": "Details"},
                    )
                    or {}
                )
                details = po.get("Details") or []
            line_nbr = int((details[0] or {}).get("LineNbr") or 1) if details else 1
            try:
                rcpt = unwrap(
                    session.put(
                        "PurchaseReceipt",
                        {
                            "Type": "Receipt",
                            "VendorID": VENDOR_CD,
                            "Hold": False,
                            "Warehouse": self.warehouse,
                            "Details": [
                                {
                                    "InventoryID": COMPONENT_CD,
                                    "POOrderType": "Normal",
                                    "POOrderNbr": order_nbr,
                                    "POLineNbr": line_nbr,
                                    "ReceiptQty": 1,
                                    "Location": LOCATION,
                                    "LotSerialNbr": lot,
                                    "ExpirationDate": "2028-12-31",
                                }
                            ],
                        },
                    )
                )
            except RuntimeError as exc:
                self.fail(f"PurchaseReceipt PUT setup failed: {exc}")
            receipt_nbr = (rcpt.get("ReceiptNbr") or "").strip()
            self.assertTrue(receipt_nbr, "PurchaseReceipt PUT returned no ReceiptNbr")
            try:
                _invoke_default(
                    session,
                    "PurchaseReceipt",
                    "ReleasePurchaseReceipt",
                    {"Type": "Receipt", "ReceiptNbr": receipt_nbr},
                )
            except RuntimeError as exc:
                self.fail(f"ReleasePurchaseReceipt setup failed: {exc}")
            status = _sql_lot_status(COMPONENT_CD, lot)
            if status != QC_HOLD:
                _force_qc_hold(COMPONENT_CD, lot)
                status = _sql_lot_status(COMPONENT_CD, lot)
            self.assertEqual(
                status,
                QC_HOLD,
                f"lot {lot} UsrQMSLotStatus={status!r} — need QC Hold on "
                f"{COMPONENT_CD} after receipt release",
            )

            try:
                created = unwrap(
                    session.put(
                        "KitAssembly",
                        {
                            "Type": KIT_TYPE,
                            "KitInventoryID": KIT_CD,
                            "Revision": "V1",
                            "Qty": 1,
                            "WarehouseID": self.warehouse,
                            "LocationID": LOCATION,
                            "Hold": False,
                        },
                    )
                )
            except RuntimeError as exc:
                self.fail(
                    f"KitAssembly header PUT failed after QC Hold lot {lot}: {exc}"
                )
            ref = (created.get("ReferenceNbr") or "").strip()
            kit_type = (created.get("Type") or KIT_TYPE).strip() or KIT_TYPE
            self.assertTrue(ref, "KitAssembly PUT returned no ReferenceNbr")
            raw = session.get_record(
                "KitAssembly",
                [kit_type, ref],
                params={"$expand": "StockComponents"},
            )
            self.assertIsNotNone(
                raw, f"KitAssembly GET {kit_type}/{ref} returned nothing"
            )
            components = raw.get("StockComponents") or []
            ech_raw = None
            ech = None
            for row in components:
                if not isinstance(row, dict):
                    continue
                body = unwrap(row)
                if (body.get("StockInventoryID") or "").strip() == COMPONENT_CD:
                    ech_raw = row
                    ech = body
                    break
            self.assertIsNotNone(
                ech,
                f"KitAssembly {ref} has no {COMPONENT_CD} stock component",
            )
            qty = ech.get("Qty") or ech.get("ComponentQty") or 0.012
            alloc_line = {
                "id": ech_raw.get("id"),
                "LineNbr": ech.get("LineNbr"),
                "StockInventoryID": COMPONENT_CD,
                "LocationID": LOCATION,
                "Allocations": [
                    {
                        "LineNbr": ech.get("LineNbr"),
                        "LocationID": LOCATION,
                        "LotSerialNbr": lot,
                        "Qty": qty,
                        "InventoryID": COMPONENT_CD,
                    }
                ],
            }
            alloc = {
                "id": raw.get("id"),
                "Type": kit_type,
                "ReferenceNbr": ref,
                "StockComponents": [alloc_line],
            }
            put = session._http.put(session._url("KitAssembly"), json=wrap(alloc))
            if put.is_error:
                try:
                    payload = put.json()
                except Exception:
                    payload = {"exceptionMessage": (put.text or "")[:500]}
                text = _error_text(payload)
                self.assertTrue(
                    _gate_message(text),
                    f"KitAssembly allocation of QC Hold lot {lot} failed "
                    f"without V15 gate message: {text}",
                )
                return

            try:
                _invoke_default(
                    session,
                    "KitAssembly",
                    "ReleaseKitAssembly",
                    {"Type": kit_type, "ReferenceNbr": ref},
                )
            except RuntimeError as exc:
                self.assertTrue(
                    _gate_message(_error_text(exc) + str(exc)),
                    f"ReleaseKitAssembly of QC Hold lot {lot} failed "
                    f"without V15 gate message: {exc}",
                )
                return

        self.fail(
            f"KitAssembly {ref} allocated and released QC Hold lot {lot} "
            f"on {COMPONENT_CD} — V15 gate did not fire"
        )


if __name__ == "__main__":
    unittest.main()
