#!/usr/bin/env -S uv run
"""T26 / V14: QMSSetup GET PUT; GitOps Quality Preferences PUT; PO receipt Release no 422."""

from __future__ import annotations

import time
import unittest

from e2e.helper import (
    DB_NAME,
    ITEM_CD,
    QMS_ENDPOINT,
    VENDOR_CD,
    client,
    company_id,
    ensure_numbering_and_role,
    ensure_published,
    instance,
    qms_get,
    qms_put,
    sql_lines,
    unwrap,
    wrap,
)
from e2e.test_functional import GITOPS_PLANS, _plan_record, _seed_ready
from e2e.test_stock_item_qms import GITOPS_STOCK_ITEMS

# GitOps Quality Preferences PUT shape (V14). This repo must not `acu apply`
# that YAML; e2e PUTs the same field set on QMS/22.200.001.
GITOPS_QMS_SETUP = {
    "InspectionOrderNumberingID": "QORD",
    "NCRNumberingID": "QNCR",
}

PXSETUP_EMPTY = (
    "The required configuration data is not entered on the Quality Preferences form."
)
WAREHOUSE = "WH-MISS-01"
LOCATION = "MAIN"


def _setup_fields(row: dict) -> tuple[str, str]:
    return (
        (row.get("InspectionOrderNumberingID") or "").strip(),
        (row.get("NCRNumberingID") or "").strip(),
    )


def _sql_setup() -> tuple[str, str] | None:
    if not instance().ssh:
        return None
    rows = sql_lines(
        "SELECT RTRIM(InspectionOrderNumberingID), RTRIM(NCRNumberingID) "
        f"FROM {DB_NAME}.dbo.UsrQMSSetup WHERE CompanyID = {company_id()}"
    )
    if not rows:
        return None
    order, ncr = rows[0].split("|")
    return order.strip(), ncr.strip()


def _invoke_default(
    session,
    entity: str,
    action: str,
    record: dict,
    timeout: float = 120.0,
):
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


class TestQmsSetupGetPutV14(unittest.TestCase):
    """V14: GET/PUT QMSSetup on QMS/22.200.001; GitOps PUT no UI/SQL."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            ensure_numbering_and_role(session)

    def test_get_after_seed_returns_qord_qncr(self) -> None:
        with client() as session:
            r = session._http.get(f"/entity/{QMS_ENDPOINT}/QMSSetup")
            session._checked(r)
            rows = r.json()
        self.assertIsInstance(rows, list)
        self.assertTrue(rows, "UsrQMSSetup empty after publish seed")
        order, ncr = _setup_fields(unwrap(rows[0]))
        self.assertEqual(order, "QORD")
        self.assertEqual(ncr, "QNCR")

    def test_gitops_put_quality_preferences_no_ui_sql(self) -> None:
        rec = dict(GITOPS_QMS_SETUP)
        with client() as session:
            qms_put(session, "QMSSetup", rec)
            rows = qms_get(session, "QMSSetup")
        self.assertIsInstance(rows, list)
        self.assertTrue(rows, "QMSSetup GET empty after PUT")
        order, ncr = _setup_fields(unwrap(rows[0] if isinstance(rows, list) else rows))
        self.assertEqual(order, rec["InspectionOrderNumberingID"])
        self.assertEqual(ncr, rec["NCRNumberingID"])
        sql_row = _sql_setup()
        if sql_row is not None:
            self.assertEqual(sql_row, (order, ncr))


class TestReceiptReleaseNoPxSetup422(unittest.TestCase):
    """V14: PO receipt Release with no QM101000 UI Save → draft order, not 422."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            reason = _seed_ready(session)
            if reason:
                raise unittest.SkipTest(reason)
            ensure_numbering_and_role(session)
            qms_put(session, "QMSSetup", GITOPS_QMS_SETUP)
            item = unwrap(session.get_record("StockItem", [ITEM_CD]) or {})
            lot_class = (
                item.get("LotSerialClass") or item.get("LotSerClass") or ""
            ).strip()
            if not lot_class:
                raise unittest.SkipTest(
                    f"{ITEM_CD} has no LotSerialClass — dock/lot e2e needs "
                    "lot-tracked items from acu-gitops-qms"
                )
            cls.warehouse = (
                item.get("DefaultWarehouseID")
                or item.get("DefaultWarehouse")
                or WAREHOUSE
            ).strip() or WAREHOUSE
            qms_put(
                session,
                "InspectionPlan",
                GITOPS_PLANS[0] if GITOPS_PLANS else _plan_record(),
            )
            qms_put(session, "StockItem", dict(GITOPS_STOCK_ITEMS[0]))

    def test_release_creates_draft_inspection_order_not_422(self) -> None:
        stamp = time.strftime("%H%M%S")
        lot = f"E2EQMS{stamp}"
        with client() as session:
            po = unwrap(
                session.put(
                    "PurchaseOrder",
                    {
                        "VendorID": VENDOR_CD,
                        "Hold": False,
                        "Details": [
                            {
                                "InventoryID": ITEM_CD,
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
                                    "InventoryID": ITEM_CD,
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
                self.fail(f"PurchaseReceipt PUT failed: {exc}")
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
                msg = str(exc)
                self.assertNotIn(
                    PXSETUP_EMPTY,
                    msg,
                    "PO receipt Release 422 PXSetup empty — UsrQMSSetup missing",
                )
                self.fail(f"ReleasePurchaseReceipt failed: {exc}")
            orders = qms_get(
                session,
                "InspectionOrder",
                params={
                    "$filter": f"LotSerialNbr eq '{lot}'",
                    "$top": "5",
                },
            )
        self.assertTrue(
            orders,
            f"expected draft InspectionOrder for lot {lot} receipt {receipt_nbr}",
        )
        body = unwrap(orders[0] if isinstance(orders, list) else orders)
        self.assertEqual((body.get("LotSerialNbr") or "").strip(), lot)
        self.assertEqual((body.get("ReceiptNbr") or "").strip(), receipt_nbr)
        self.assertNotIn(PXSETUP_EMPTY, str(body))


if __name__ == "__main__":
    unittest.main()
