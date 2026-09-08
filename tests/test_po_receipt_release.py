#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T6 / V1 / V9: POReceiptEntry_Extension Release QC Hold + draft inspection order."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "POReceiptEntry_Extension.cs"
RULES_CS = ROOT / "src" / "Lab5.QMS" / "QMSReceiptReleaseRules.cs"
LOT_CS = ROOT / "src" / "Lab5.QMS" / "QMSLotStatus.cs"
STATUS_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSInspectionOrderStatus.cs"

QC_HOLD = "QC Hold"
RELEASED = "Released"
QUARANTINE = "Quarantine"
STATUS_OPEN = "O"
OVERALL_PENDING = "P"


def requires_inspection(required: bool | None) -> bool:
    return required is True


def has_lot(lot_serial_nbr: str | None) -> bool:
    return lot_serial_nbr is not None and lot_serial_nbr.strip() != ""


def three_way_link_consistent(
    receipt_nbr: str | None,
    lot_serial_nbr: str | None,
    order_receipt_nbr: str | None,
    order_lot_serial_nbr: str | None,
) -> bool:
    return receipt_nbr == order_receipt_nbr and lot_serial_nbr == order_lot_serial_nbr


def compact_token(value: str | None, width: int) -> str:
    if width <= 0:
        return ""
    if not value:
        return "0" * width
    alnum = "".join(c.upper() for c in value if c.isalnum())
    if not alnum:
        return "0" * width
    if len(alnum) <= width:
        return alnum.zfill(width)
    return alnum[-width:]


def draft_order_nbr(receipt_nbr: str | None, lot_serial_nbr: str | None) -> str:
    return "Q" + compact_token(receipt_nbr, 7) + compact_token(lot_serial_nbr, 7)


def seed_draft_order(
    inspection_order_nbr: str,
    inventory_id: int | None,
    lot_serial_nbr: str | None,
    vendor_id: int | None,
    receipt_nbr: str | None,
    plan_id: str | None,
) -> dict:
    return {
        "InspectionOrderNbr": inspection_order_nbr,
        "InventoryID": inventory_id,
        "LotSerialNbr": lot_serial_nbr,
        "VendorID": vendor_id,
        "ReceiptNbr": receipt_nbr,
        "PlanID": plan_id,
        "Status": STATUS_OPEN,
        "OverallEvaluation": OVERALL_PENDING,
    }


class TestRequiresInspectionV1(unittest.TestCase):
    def test_true_requires_gate(self) -> None:
        self.assertTrue(requires_inspection(True))

    def test_false_skips_gate(self) -> None:
        self.assertFalse(requires_inspection(False))

    def test_none_skips_gate(self) -> None:
        self.assertFalse(requires_inspection(None))

    def test_csharp_requires_inspection_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn("public static bool RequiresInspection(bool? required)", src)
        self.assertIn("return required == true;", src)
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("itemExt?.UsrQMSInspectionRequired", graph)
        self.assertIn(
            "if (!QMSReceiptReleaseRules.RequiresInspection(itemExt?.UsrQMSInspectionRequired))",
            graph,
        )


class TestQcHoldNotReleasedV1(unittest.TestCase):
    def test_lot_status_constants(self) -> None:
        src = LOT_CS.read_text(encoding="utf-8")
        self.assertIn(f'public const string QcHold = "{QC_HOLD}"', src)
        self.assertIn(f'public const string Released = "{RELEASED}"', src)
        self.assertIn(f'public const string Quarantine = "{QUARANTINE}"', src)

    def test_release_sets_qc_hold_not_released(self) -> None:
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("UpdateLotStatus(item.InventoryID, split.LotSerialNbr, QMSLotStatus.QcHold)", graph)
        self.assertNotIn("QMSLotStatus.Released", graph)
        self.assertIn("QMSLotIssueGate.WriteLotStatus(Base, inventoryID, lotSerialNbr, lotStatus)", graph)

    def test_draft_order_open_pending(self) -> None:
        order = seed_draft_order("Q0000001LOT0001", 42, "LOT-1", 7, "PR000001", "QPLAN-BOT")
        self.assertEqual(order["Status"], STATUS_OPEN)
        self.assertEqual(order["OverallEvaluation"], OVERALL_PENDING)
        self.assertEqual(order["PlanID"], "QPLAN-BOT")
        self.assertEqual(order["LotSerialNbr"], "LOT-1")
        self.assertEqual(order["VendorID"], 7)
        self.assertEqual(order["ReceiptNbr"], "PR000001")
        status = STATUS_CS.read_text(encoding="utf-8")
        self.assertIn('public const string Open = "O"', status)
        self.assertIn('public const string Pending = "P"', status)
        rules = RULES_CS.read_text(encoding="utf-8")
        self.assertIn("order.Status = QMSInspectionOrderStatus.Open;", rules)
        self.assertIn("order.OverallEvaluation = QMSOverallEvaluation.Pending;", rules)
        self.assertIn("order.PlanID = planID;", rules)
        self.assertIn("order.LotSerialNbr = lotSerialNbr;", rules)
        self.assertIn("order.VendorID = vendorID;", rules)
        self.assertIn("order.ReceiptNbr = receiptNbr;", rules)


class TestThreeWayLinkV9(unittest.TestCase):
    def test_receipt_lot_order_match(self) -> None:
        self.assertTrue(
            three_way_link_consistent("PR000001", "LOT-A", "PR000001", "LOT-A")
        )

    def test_mismatched_receipt_fails(self) -> None:
        self.assertFalse(
            three_way_link_consistent("PR000001", "LOT-A", "PR000002", "LOT-A")
        )

    def test_mismatched_lot_fails(self) -> None:
        self.assertFalse(
            three_way_link_consistent("PR000001", "LOT-A", "PR000001", "LOT-B")
        )

    def test_empty_lot_skips_order(self) -> None:
        self.assertFalse(has_lot(None))
        self.assertFalse(has_lot(""))
        self.assertFalse(has_lot("   "))
        self.assertTrue(has_lot("LOT-A"))
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("if (!QMSReceiptReleaseRules.HasLot(split.LotSerialNbr))", graph)

    def test_existing_receipt_lot_skips_duplicate(self) -> None:
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("QMSInspectionOrder.receiptNbr, Equal<Required<QMSInspectionOrder.receiptNbr>>", graph)
        self.assertIn("QMSInspectionOrder.lotSerialNbr, Equal<Required<QMSInspectionOrder.lotSerialNbr>>", graph)
        self.assertIn("if (existing != null)", graph)

    def test_seed_copies_receipt_and_lot_from_split(self) -> None:
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("split.LotSerialNbr", graph)
        self.assertIn("doc.ReceiptNbr", graph)
        self.assertIn("doc.VendorID", graph)
        self.assertIn("itemExt.UsrQMSInspectionPlanID", graph)
        self.assertIn("QMSReceiptReleaseRules.SeedDraftOrder", graph)
        rules = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static bool ThreeWayLinkConsistent(\n"
            "            string receiptNbr,\n"
            "            string lotSerialNbr,\n"
            "            string orderReceiptNbr,\n"
            "            string orderLotSerialNbr)",
            rules,
        )
        self.assertIn(
            "string.Equals(receiptNbr, orderReceiptNbr, StringComparison.Ordinal)",
            rules,
        )
        self.assertIn(
            "string.Equals(lotSerialNbr, orderLotSerialNbr, StringComparison.Ordinal)",
            rules,
        )


class TestDraftOrderNbr(unittest.TestCase):
    def test_compact_pads_and_strips(self) -> None:
        self.assertEqual(compact_token("PR-0001", 7), "00PR0001"[-7:])
        self.assertEqual(compact_token("PR0001", 7), "0PR0001")
        self.assertEqual(compact_token(None, 7), "0000000")
        self.assertEqual(compact_token("LOT-ABC-999", 7), "OTABC999"[-7:])

    def test_nbr_is_fifteen_chars(self) -> None:
        nbr = draft_order_nbr("PR0000123", "LOT-ABC-999")
        self.assertEqual(len(nbr), 15)
        self.assertTrue(nbr.startswith("Q"))
        self.assertEqual(nbr, "Q" + compact_token("PR0000123", 7) + compact_token("LOT-ABC-999", 7))

    def test_csharp_draft_nbr_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn('return "Q" + CompactToken(receiptNbr, 7) + CompactToken(lotSerialNbr, 7);', src)
        self.assertIn("alnum.PadLeft(width, '0')", src)
        self.assertIn("alnum.Substring(alnum.Length - width)", src)
        self.assertIn("char.IsLetterOrDigit(c)", src)


class TestGraphOverride(unittest.TestCase):
    def test_extension_overrides_release_after_base(self) -> None:
        src = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "class POReceiptEntry_Extension : PXGraphExtension<POReceiptEntry>",
            src,
        )
        self.assertIn("public delegate IEnumerable ReleaseDelegate(PXAdapter adapter);", src)
        self.assertIn("[PXOverride]", src)
        self.assertIn(
            "public IEnumerable Release(PXAdapter adapter, ReleaseDelegate baseMethod)",
            src,
        )
        base_at = src.index("baseMethod(adapter)")
        gate_at = src.index("ApplyInspectionGate(doc)")
        self.assertLess(base_at, gate_at)
        self.assertIn("PXSelect<POReceiptLine,", src)
        self.assertIn("PXSelect<POReceiptLineSplit,", src)
        self.assertIn("PXGraph.CreateInstance<QMSInspectionOrderEntry>()", src)
        self.assertIn("QMSLotIssueGate.WriteLotStatus(Base, inventoryID, lotSerialNbr, lotStatus)", src)
        gate = (ROOT / "src" / "Lab5.QMS" / "QMSLotIssueGate.cs").read_text(encoding="utf-8")
        self.assertIn("INLotSerialStatus.lotSerialNbr", gate)


if __name__ == "__main__":
    unittest.main()
