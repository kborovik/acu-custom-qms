#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T7 / V5 / V6 / V9: ReleaseLotDecision pass/fail lot flip + NCR auto-create."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_CS = ROOT / "QMS" / "Lab5.QMS" / "Graph" / "QMSInspectionOrderEntry.cs"
RULES_CS = ROOT / "QMS" / "Lab5.QMS" / "QMSLotDecisionRules.cs"
LOT_CS = ROOT / "QMS" / "Lab5.QMS" / "QMSLotStatus.cs"
NCR_RULES_CS = ROOT / "QMS" / "Lab5.QMS" / "QMSNonConformanceRules.cs"
TS = (
    ROOT
    / "QMS"
    / "FrontendSources"
    / "screen"
    / "src"
    / "development"
    / "screens"
    / "QM"
    / "QM301000"
    / "QM301000.ts"
)

QC_HOLD = "QC Hold"
RELEASED = "Released"
QUARANTINE = "Quarantine"
STATUS_OPEN = "O"
STATUS_COMPLETED = "C"
STATUS_CANCELLED = "X"
OVERALL_PENDING = "P"
OVERALL_PASS = "V"
OVERALL_FAIL = "F"
STATUS_NCR_OPEN = "O"
SEVERITY_CRITICAL = "C"
AUTOMATED_OOS = (
    "Automated OOS Failure: Laboratory results breached acceptable tolerances."
)
QUARANTINE_RTV = "Quarantine Segregation & RTV Claim"


def can_release(overall_evaluation: str | None, order_status: str | None) -> bool:
    if order_status in (STATUS_COMPLETED, STATUS_CANCELLED):
        return False
    return overall_evaluation in (OVERALL_PASS, OVERALL_FAIL)


def target_lot_status(overall_evaluation: str | None) -> str:
    if overall_evaluation == OVERALL_PASS:
        return RELEASED
    if overall_evaluation == OVERALL_FAIL:
        return QUARANTINE
    return QC_HOLD


def should_create_ncr(overall_evaluation: str | None) -> bool:
    return overall_evaluation == OVERALL_FAIL


def is_allocatable(lot_status: str | None) -> bool:
    return lot_status == RELEASED


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


def ncr_nbr(inspection_order_nbr: str | None) -> str:
    return "N" + compact_token(inspection_order_nbr, 14)


def seed_from_failed_order(
    inspection_order_nbr: str | None,
    inventory_id: int | None,
    lot_serial_nbr: str | None,
    vendor_id: int | None,
    receipt_nbr: str | None,
) -> dict:
    return {
        "NCRNbr": ncr_nbr(inspection_order_nbr),
        "InspectionOrderNbr": inspection_order_nbr,
        "InventoryID": inventory_id,
        "LotSerialNbr": lot_serial_nbr,
        "VendorID": vendor_id,
        "ReceiptNbr": receipt_nbr,
        "Status": STATUS_NCR_OPEN,
        "Severity": SEVERITY_CRITICAL,
        "Description": AUTOMATED_OOS,
        "ActionRequired": QUARANTINE_RTV,
        "InventoryHoldStatus": QUARANTINE,
    }


def apply_lot_decision(
    overall_evaluation: str,
    order_status: str,
    inspection_order_nbr: str,
    inventory_id: int,
    lot_serial_nbr: str,
    vendor_id: int,
    receipt_nbr: str,
) -> dict | None:
    if not can_release(overall_evaluation, order_status):
        return None
    lot = target_lot_status(overall_evaluation)
    ncr = None
    if should_create_ncr(overall_evaluation):
        ncr = seed_from_failed_order(
            inspection_order_nbr,
            inventory_id,
            lot_serial_nbr,
            vendor_id,
            receipt_nbr,
        )
    return {
        "LotStatus": lot,
        "Status": STATUS_COMPLETED,
        "ReceiptNbr": receipt_nbr,
        "LotSerialNbr": lot_serial_nbr,
        "NCR": ncr,
        "Allocatable": is_allocatable(lot),
    }


class TestPassPathV5(unittest.TestCase):
    def test_pass_releases_lot_and_completes_order(self) -> None:
        outcome = apply_lot_decision(
            OVERALL_PASS, STATUS_OPEN, "Q0000001LOT0001", 42, "LOT-A", 7, "PR000001"
        )
        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertEqual(outcome["LotStatus"], RELEASED)
        self.assertEqual(outcome["Status"], STATUS_COMPLETED)
        self.assertIsNone(outcome["NCR"])
        self.assertTrue(outcome["Allocatable"])

    def test_csharp_pass_path_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static string TargetLotStatus(string overallEvaluation)",
            src,
        )
        self.assertIn("return QMSLotStatus.Released;", src)
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("public PXAction<QMSInspectionOrder> ReleaseLotDecision;", graph)
        self.assertIn(
            "QMSLotDecisionRules.TargetLotStatus(order.OverallEvaluation)", graph
        )
        self.assertIn("order.Status = QMSInspectionOrderStatus.Completed;", graph)
        self.assertIn(
            "UpdateLotStatus(order.InventoryID, order.LotSerialNbr, lotStatus)", graph
        )


class TestFailPathV6(unittest.TestCase):
    def test_fail_quarantines_lot_inserts_ncr_halts_allocation(self) -> None:
        outcome = apply_lot_decision(
            OVERALL_FAIL, STATUS_OPEN, "Q0000001LOT0001", 42, "LOT-A", 7, "PR000001"
        )
        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertEqual(outcome["LotStatus"], QUARANTINE)
        self.assertEqual(outcome["Status"], STATUS_COMPLETED)
        self.assertFalse(outcome["Allocatable"])
        ncr = outcome["NCR"]
        self.assertIsNotNone(ncr)
        assert ncr is not None
        self.assertEqual(ncr["InspectionOrderNbr"], "Q0000001LOT0001")
        self.assertEqual(ncr["LotSerialNbr"], "LOT-A")
        self.assertEqual(ncr["ReceiptNbr"], "PR000001")
        self.assertEqual(ncr["InventoryHoldStatus"], QUARANTINE)
        self.assertEqual(ncr["Severity"], SEVERITY_CRITICAL)
        self.assertEqual(ncr["Description"], AUTOMATED_OOS)
        self.assertEqual(ncr["NCRNbr"], ncr_nbr("Q0000001LOT0001"))

    def test_quarantine_and_qc_hold_not_allocatable(self) -> None:
        self.assertFalse(is_allocatable(QUARANTINE))
        self.assertFalse(is_allocatable(QC_HOLD))
        self.assertTrue(is_allocatable(RELEASED))
        self.assertFalse(is_allocatable(None))

    def test_csharp_fail_path_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn("return QMSLotStatus.Quarantine;", src)
        self.assertIn(
            "public static bool ShouldCreateNcr(string overallEvaluation)",
            src,
        )
        self.assertIn("return overallEvaluation == QMSOverallEvaluation.Fail;", src)
        self.assertIn("public static bool IsAllocatable(string lotStatus)", src)
        self.assertIn("return lotStatus == QMSLotStatus.Released;", src)
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "QMSLotDecisionRules.ShouldCreateNcr(order.OverallEvaluation)", graph
        )
        self.assertIn("CreateNcrFromFailedOrder(order)", graph)
        self.assertIn("QMSNonConformanceRules.SeedFromFailedOrder(", graph)
        self.assertIn("PXGraph.CreateInstance<QMSNonConformanceEntry>()", graph)
        self.assertIn(
            "QMSNonConformance.inspectionOrderNbr, Equal<Required<QMSNonConformance.inspectionOrderNbr>>",
            graph,
        )
        ncr_rules = NCR_RULES_CS.read_text(encoding="utf-8")
        self.assertIn(AUTOMATED_OOS, ncr_rules)
        self.assertIn(
            "ncr.InventoryHoldStatus = QMSInventoryHoldStatus.Quarantine;", ncr_rules
        )


class TestThreeWayLinkV9(unittest.TestCase):
    def test_ncr_copies_receipt_and_lot_from_order(self) -> None:
        receipt = "PR000001"
        lot = "LOT-A"
        outcome = apply_lot_decision(
            OVERALL_FAIL, STATUS_OPEN, "Q0000001LOT0001", 42, lot, 7, receipt
        )
        assert outcome is not None
        self.assertEqual(outcome["ReceiptNbr"], receipt)
        self.assertEqual(outcome["LotSerialNbr"], lot)
        ncr = outcome["NCR"]
        assert ncr is not None
        self.assertEqual(ncr["ReceiptNbr"], receipt)
        self.assertEqual(ncr["LotSerialNbr"], lot)

    def test_pass_does_not_rewrite_receipt_or_lot(self) -> None:
        outcome = apply_lot_decision(
            OVERALL_PASS, STATUS_OPEN, "Q0000001LOT0001", 42, "LOT-A", 7, "PR000001"
        )
        assert outcome is not None
        self.assertEqual(outcome["ReceiptNbr"], "PR000001")
        self.assertEqual(outcome["LotSerialNbr"], "LOT-A")

    def test_csharp_seed_uses_order_receipt_and_lot(self) -> None:
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("order.LotSerialNbr,", graph)
        self.assertIn("order.VendorID,", graph)
        self.assertIn("order.ReceiptNbr);", graph)
        self.assertIn("order.InspectionOrderNbr,", graph)
        self.assertIn("order.InventoryID,", graph)
        action = graph[
            graph.index("protected virtual IEnumerable releaseLotDecision") :
        ]
        action = action[: action.index("protected virtual void UpdateLotStatus")]
        self.assertNotIn("order.ReceiptNbr =", action)
        self.assertNotIn("order.LotSerialNbr =", action)


class TestLotStatusSetILot(unittest.TestCase):
    def test_lot_status_constants(self) -> None:
        src = LOT_CS.read_text(encoding="utf-8")
        self.assertIn(f'public const string QcHold = "{QC_HOLD}"', src)
        self.assertIn(f'public const string Released = "{RELEASED}"', src)
        self.assertIn(f'public const string Quarantine = "{QUARANTINE}"', src)

    def test_pending_keeps_qc_hold(self) -> None:
        self.assertEqual(target_lot_status(OVERALL_PENDING), QC_HOLD)
        self.assertFalse(can_release(OVERALL_PENDING, STATUS_OPEN))
        self.assertIsNone(
            apply_lot_decision(
                OVERALL_PENDING,
                STATUS_OPEN,
                "Q0000001LOT0001",
                42,
                "LOT-A",
                7,
                "PR000001",
            )
        )

    def test_completed_or_cancelled_blocked(self) -> None:
        self.assertFalse(can_release(OVERALL_PASS, STATUS_COMPLETED))
        self.assertFalse(can_release(OVERALL_FAIL, STATUS_CANCELLED))
        self.assertTrue(can_release(OVERALL_PASS, STATUS_OPEN))
        self.assertTrue(can_release(OVERALL_FAIL, STATUS_OPEN))

    def test_csharp_can_release_and_ncr_nbr_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static bool CanRelease(string overallEvaluation, string orderStatus)",
            src,
        )
        self.assertIn("orderStatus == QMSInspectionOrderStatus.Completed", src)
        self.assertIn("orderStatus == QMSInspectionOrderStatus.Cancelled", src)
        self.assertIn("overallEvaluation == QMSOverallEvaluation.Pass", src)
        self.assertIn("overallEvaluation == QMSOverallEvaluation.Fail", src)
        self.assertIn(
            'return "N" + QMSReceiptReleaseRules.CompactToken(inspectionOrderNbr, 14);',
            src,
        )
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "QMSLotDecisionRules.CanRelease(order.OverallEvaluation, order.Status)",
            graph,
        )
        self.assertIn(
            "Overall evaluation must be Pass or Fail on an open inspection order.",
            graph,
        )
        self.assertIn(
            "QMSLotIssueGate.WriteLotStatus(this, inventoryID, lotSerialNbr, lotStatus)",
            graph,
        )
        gate = (ROOT / "QMS" / "Lab5.QMS" / "QMSLotIssueGate.cs").read_text(
            encoding="utf-8"
        )
        self.assertIn("PXDatabase.Update<INLotSerialStatusByCostCenter>(", gate)
        self.assertIn('new PXDataField("UsrQMSLotStatus")', gate)
        self.assertIn("INLotSerialStatus.lotSerialNbr", gate)
        self.assertIn("INLotSerialStatusByCostCenter.lotSerialNbr", gate)
        self.assertNotIn("graph.Caches[typeof(INLotSerialStatus)].Update(lot)", gate)
        self.assertNotIn(
            "graph.Caches[typeof(INLotSerialStatusByCostCenter)].Update(lot)",
            gate,
        )
        ext = (ROOT / "QMS" / "Lab5.QMS" / "DAC" / "INLotSerialStatusExt.cs").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "class INLotSerialStatusExt : PXCacheExtension<INLotSerialStatus>",
            ext,
        )
        self.assertIn("UsrQMSLotStatus", ext)
        sql = (ROOT / "QMS" / "SQL" / "CreateQMSTables.sql").read_text(encoding="utf-8")
        self.assertIn(
            "COL_LENGTH(N'dbo.INLotSerialStatus', N'UsrQMSLotStatus')",
            sql,
        )
        self.assertIn(
            "COL_LENGTH(N'dbo.INLotSerialStatusByCostCenter', N'UsrQMSLotStatus')",
            sql,
        )
        ts = TS.read_text(encoding="utf-8")
        self.assertIn("ReleaseLotDecision: PXActionState", ts)
        self.assertIn("EvaluateResults: PXActionState", ts)


class TestNcrNbr(unittest.TestCase):
    def test_fifteen_chars(self) -> None:
        nbr = ncr_nbr("Q0000001LOT0001")
        self.assertEqual(len(nbr), 15)
        self.assertTrue(nbr.startswith("N"))
        self.assertEqual(nbr, "N" + compact_token("Q0000001LOT0001", 14))

    def test_csharp_ncr_nbr_used_on_insert(self) -> None:
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "ncr.NCRNbr = QMSLotDecisionRules.NcrNbr(order.InspectionOrderNbr);", graph
        )


if __name__ == "__main__":
    unittest.main()
