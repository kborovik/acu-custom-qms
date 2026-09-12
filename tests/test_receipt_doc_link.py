#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T55 / V24: QM301000 QM302000 ReceiptNbr AllowEdit to PO302000; captions."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acuqms.paths import FRONTEND_SCREENS_REL  # noqa: E402

ORDER_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionOrder.cs"
NCR_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSNonConformance.cs"
PLAN_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionPlan.cs"
ITEM_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "InventoryItemExt.cs"
ORDER_ASPX = ROOT / "QMS" / "Pages" / "QM" / "QM301000.aspx"
NCR_ASPX = ROOT / "QMS" / "Pages" / "QM" / "QM302000.aspx"
ORDER_TS = ROOT / FRONTEND_SCREENS_REL / "QM" / "QM301000" / "QM301000.ts"
NCR_TS = ROOT / FRONTEND_SCREENS_REL / "QM" / "QM302000" / "QM302000.ts"
ENDPOINT_XML = ROOT / "QMS" / "_project" / "QMS.xml"

ALLOW_EDIT_RECEIPT = re.compile(
    r"@controlConfig\(\{\s*allowEdit:\s*true\s*\}\)\s+ReceiptNbr: PXFieldState"
)
ALLOW_EDIT_PLAN = re.compile(
    r"@controlConfig\(\{[^}]*allowEdit:\s*true[^}]*\}\)\s+PlanID:"
)
ASPX_RECEIPT = re.compile(r'<px:PXSelector ID="edReceiptNbr"[^>]*AllowEdit="True"')
ASPX_PLAN_ALLOW = re.compile(r'<px:PXSelector ID="edPlanID"[^>]*AllowEdit="True"')


def _region(src: str, name: str) -> str:
    match = re.search(
        rf"#region {re.escape(name)}\n(.*?)#endregion",
        src,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing #region {name}")
    return match.group(1)


class TestV24_ReceiptDocLink(unittest.TestCase):
    """V24: Purchase Receipt AllowEdit + Inspection Plan caption; REST names stay."""

    def test_dac_display_names(self) -> None:
        order = ORDER_CS.read_text(encoding="utf-8")
        receipt = _region(order, "ReceiptNbr")
        self.assertIn('[PXUIField(DisplayName = "PurchaseReceipt")]', receipt)
        self.assertIn("typeof(Search<POReceipt.receiptNbr>)", receipt)
        self.assertNotIn("AllowEdit = true", receipt)
        plan = _region(order, "PlanID")
        self.assertIn('[PXUIField(DisplayName = "InspectionPlan")]', plan)
        self.assertNotIn("AllowEdit = true", plan)

        ncr = _region(NCR_CS.read_text(encoding="utf-8"), "ReceiptNbr")
        self.assertIn('[PXUIField(DisplayName = "PurchaseReceipt")]', ncr)
        self.assertIn("typeof(Search<POReceipt.receiptNbr>)", ncr)
        self.assertNotIn("AllowEdit = true", ncr)

        plan_master = _region(PLAN_CS.read_text(encoding="utf-8"), "PlanID")
        self.assertIn('[PXUIField(DisplayName = "PlanID"', plan_master)
        item_plan = _region(
            ITEM_CS.read_text(encoding="utf-8"), "UsrQMSInspectionPlanID"
        )
        self.assertIn('[PXUIField(DisplayName = "InspectionPlan")]', item_plan)

    def test_aspx_allow_edit_receipt_not_plan(self) -> None:
        order_aspx = ORDER_ASPX.read_text(encoding="utf-8")
        ncr_aspx = NCR_ASPX.read_text(encoding="utf-8")
        self.assertRegex(order_aspx, ASPX_RECEIPT)
        self.assertRegex(ncr_aspx, ASPX_RECEIPT)
        self.assertNotRegex(order_aspx, ASPX_PLAN_ALLOW)

    def test_ts_controlconfig_allowedit_receipt_not_plan(self) -> None:
        order_ts = ORDER_TS.read_text(encoding="utf-8")
        ncr_ts = NCR_TS.read_text(encoding="utf-8")
        self.assertRegex(order_ts, ALLOW_EDIT_RECEIPT)
        self.assertRegex(ncr_ts, ALLOW_EDIT_RECEIPT)
        self.assertNotRegex(order_ts, ALLOW_EDIT_PLAN)
        self.assertIn("PlanID: PXFieldState", order_ts)

    def test_rest_field_names_stay(self) -> None:
        xml = ENDPOINT_XML.read_text(encoding="utf-8")
        self.assertIn('<Field name="ReceiptNbr" type="StringValue" />', xml)
        self.assertIn('<Field name="PlanID" type="StringValue" />', xml)
        self.assertNotIn('<Field name="PurchaseReceipt"', xml)
        self.assertNotIn('<Field name="InspectionPlan"', xml)
        self.assertNotIn('name="Purchase Receipt"', xml)
        self.assertNotIn('name="Inspection Plan"', xml)


if __name__ == "__main__":
    unittest.main()
