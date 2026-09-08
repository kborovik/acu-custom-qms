#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T27 / V15 / V1: Kit Assembly + IN Issue refuse QC Hold and Quarantine lots."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "KitAssemblyEntry_Extension.cs"
ISSUE_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "INIssueEntry_Extension.cs"
GATE_CS = ROOT / "src" / "Lab5.QMS" / "QMSLotIssueGate.cs"
RULES_CS = ROOT / "src" / "Lab5.QMS" / "QMSLotDecisionRules.cs"
LOT_CS = ROOT / "src" / "Lab5.QMS" / "QMSLotStatus.cs"

QC_HOLD = "QC Hold"
RELEASED = "Released"
QUARANTINE = "Quarantine"

REFUSE_SNIPPET = (
    "QC Hold and Quarantine lots cannot be issued; issue is allowed only when Released."
)


def is_allocatable(lot_status: str | None) -> bool:
    return lot_status == RELEASED


def can_issue(lot_status: str | None) -> bool:
    if lot_status is None or not str(lot_status).strip():
        return True
    return is_allocatable(lot_status)


def refuse_issue_message(lot_serial_nbr: str | None, lot_status: str | None) -> str:
    return (
        f"Cannot issue lot '{lot_serial_nbr}' with QMS lot status '{lot_status}'. "
        + REFUSE_SNIPPET
    )


class TestCanIssueOracleV15(unittest.TestCase):
    def test_released_allowed(self) -> None:
        self.assertTrue(can_issue(RELEASED))
        self.assertTrue(is_allocatable(RELEASED))

    def test_qc_hold_and_quarantine_refused(self) -> None:
        self.assertFalse(can_issue(QC_HOLD))
        self.assertFalse(can_issue(QUARANTINE))
        self.assertFalse(is_allocatable(QC_HOLD))
        self.assertFalse(is_allocatable(QUARANTINE))

    def test_null_or_empty_not_qms_gated(self) -> None:
        self.assertTrue(can_issue(None))
        self.assertTrue(can_issue(""))
        self.assertTrue(can_issue("   "))
        self.assertFalse(is_allocatable(None))

    def test_refuse_message_names_hold_quarantine_released(self) -> None:
        msg = refuse_issue_message("NB-ECH-25001", QC_HOLD)
        self.assertIn(QC_HOLD, msg)
        self.assertIn(QUARANTINE, msg)
        self.assertIn(RELEASED, msg)
        self.assertIn("NB-ECH-25001", msg)

    def test_csharp_can_issue_calls_is_allocatable(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn("public static bool IsAllocatable(string lotStatus)", src)
        self.assertIn("return lotStatus == QMSLotStatus.Released;", src)
        self.assertIn("public static bool CanIssue(string lotStatus)", src)
        self.assertIn("if (string.IsNullOrWhiteSpace(lotStatus))", src)
        self.assertIn("return true;", src)
        self.assertIn("return IsAllocatable(lotStatus);", src)
        self.assertIn("public static string RefuseIssueMessage(", src)
        self.assertIn(REFUSE_SNIPPET, src)
        lot = LOT_CS.read_text(encoding="utf-8")
        self.assertIn(f'public const string QcHold = "{QC_HOLD}"', lot)
        self.assertIn(f'public const string Released = "{RELEASED}"', lot)
        self.assertIn(f'public const string Quarantine = "{QUARANTINE}"', lot)


class TestKitAssemblyGraphExtensionV15(unittest.TestCase):
    def test_extends_kit_assembly_entry_in307000(self) -> None:
        src = KIT_CS.read_text(encoding="utf-8")
        self.assertIn(
            "class KitAssemblyEntry_Extension : PXGraphExtension<KitAssemblyEntry>",
            src,
        )
        self.assertIn("IN307000", src)
        self.assertIn("public static bool IsActive()", src)
        self.assertIn("[PXOverride]", src)
        self.assertIn(
            "public IEnumerable Release(PXAdapter adapter, ReleaseDelegate baseMethod)",
            src,
        )
        self.assertIn("public void Persist(PersistDelegate baseMethod)", src)
        self.assertIn("AssertLots();", src)
        self.assertIn("return baseMethod(adapter);", src)
        self.assertIn("baseMethod();", src)

    def test_component_lot_field_verifying_and_persisting(self) -> None:
        src = KIT_CS.read_text(encoding="utf-8")
        self.assertIn(
            "protected virtual void INComponentTranSplit_LotSerialNbr_FieldVerifying(",
            src,
        )
        self.assertIn(
            "protected virtual void INComponentTran_LotSerialNbr_FieldVerifying(",
            src,
        )
        self.assertIn(
            "protected virtual void INComponentTranSplit_RowPersisting(",
            src,
        )
        self.assertIn("QMSLotIssueGate.ThrowIfNotIssuable(", src)
        self.assertIn("QMSLotIssueGate.AssertKitLots(", src)
        self.assertIn("true);", src)


class TestIssueGraphExtensionV15(unittest.TestCase):
    def test_extends_in_issue_entry_in302000(self) -> None:
        src = ISSUE_CS.read_text(encoding="utf-8")
        self.assertIn(
            "class INIssueEntry_Extension : PXGraphExtension<INIssueEntry>",
            src,
        )
        self.assertIn("IN302000", src)
        self.assertIn(
            "public IEnumerable Release(PXAdapter adapter, ReleaseDelegate baseMethod)",
            src,
        )
        self.assertIn("public void Persist(PersistDelegate baseMethod)", src)
        self.assertIn("QMSLotIssueGate.AssertIssueLots(", src)
        self.assertIn(
            "protected virtual void INTranSplit_LotSerialNbr_FieldVerifying(",
            src,
        )
        self.assertIn("QMSLotIssueGate.ThrowIfNotIssuable(", src)


class TestSharedGateWiresIsAllocatable(unittest.TestCase):
    def test_gate_reads_usrqms_lot_status_and_can_issue(self) -> None:
        src = GATE_CS.read_text(encoding="utf-8")
        self.assertIn("INLotSerialStatusExt", src)
        self.assertIn("ext.UsrQMSLotStatus", src)
        self.assertIn("QMSLotDecisionRules.CanIssue(status)", src)
        self.assertIn("QMSLotDecisionRules.RefuseIssueMessage(lotSerialNbr, status)", src)
        self.assertIn("throw new PXException(message);", src)
        self.assertIn("throw new PXSetPropertyException(message);", src)
        self.assertIn("typeof(INComponentTranSplit)", src)
        self.assertIn("typeof(INTranSplit)", src)
        self.assertNotIn("lotStatus == QMSLotStatus.QcHold", src)
        self.assertNotIn('== "QC Hold"', src)


if __name__ == "__main__":
    unittest.main()
