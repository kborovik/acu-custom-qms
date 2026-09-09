#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T5 / V6: NCR DAC, QMSNonConformanceEntry, QM.30.20.00, CloseNCR, fail-path seed."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAC_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSNonConformance.cs"
STATUS_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSNonConformanceStatus.cs"
GRAPH_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "QMSNonConformanceEntry.cs"
RULES_CS = ROOT / "src" / "Lab5.QMS" / "QMSNonConformanceRules.cs"
ASPX = ROOT / "Pages_QM" / "QM302000.aspx"
SQL = ROOT / "Scripts" / "CreateQMSTables.sql"

STATUS_OPEN = "O"
STATUS_IN_INVESTIGATION = "I"
STATUS_CLOSED = "C"
STATUS_VOID = "V"
SEVERITY_CRITICAL = "C"
SEVERITY_MAJOR = "M"
SEVERITY_MINOR = "m"
HOLD_QUARANTINE = "Quarantine"
HOLD_REJECTED = "Rejected"
AUTOMATED_OOS = (
    "Automated OOS Failure: Laboratory results breached acceptable tolerances."
)
QUARANTINE_RTV = "Quarantine Segregation & RTV Claim"

NCR_FIELDS = (
    "NCRNbr",
    "Status",
    "InspectionOrderNbr",
    "InventoryID",
    "LotSerialNbr",
    "VendorID",
    "ReceiptNbr",
    "Severity",
    "NonConformanceType",
    "RootCauseCategory",
    "AssignedQAOfficer",
    "Description",
    "ActionRequired",
    "InventoryHoldStatus",
    "NoteID",
    "CreatedByID",
    "CreatedDateTime",
    "LastModifiedByID",
    "LastModifiedDateTime",
)

SUMMARY_FIELDS = (
    "NCRNbr",
    "Status",
    "InspectionOrderNbr",
    "InventoryID",
    "LotSerialNbr",
    "VendorID",
    "ReceiptNbr",
    "Severity",
    "NonConformanceType",
    "RootCauseCategory",
    "AssignedQAOfficer",
    "Description",
    "ActionRequired",
    "InventoryHoldStatus",
)

SQL_COLUMNS = (
    "NCRNbr",
    "Status",
    "InspectionOrderNbr",
    "InventoryID",
    "LotSerialNbr",
    "VendorID",
    "ReceiptNbr",
    "Severity",
    "NonConformanceType",
    "RootCauseCategory",
    "AssignedQAOfficer",
    "Description",
    "ActionRequired",
    "InventoryHoldStatus",
    "NoteID",
)


def can_close(root_cause_category: str | None) -> bool:
    return root_cause_category is not None and root_cause_category.strip() != ""


def seed_from_failed_order(
    inspection_order_nbr: str | None,
    inventory_id: int | None,
    lot_serial_nbr: str | None,
    vendor_id: int | None,
    receipt_nbr: str | None,
) -> dict:
    return {
        "InspectionOrderNbr": inspection_order_nbr,
        "InventoryID": inventory_id,
        "LotSerialNbr": lot_serial_nbr,
        "VendorID": vendor_id,
        "ReceiptNbr": receipt_nbr,
        "Status": STATUS_OPEN,
        "Severity": SEVERITY_CRITICAL,
        "Description": AUTOMATED_OOS,
        "ActionRequired": QUARANTINE_RTV,
        "InventoryHoldStatus": HOLD_QUARANTINE,
    }


def _table_block(sql: str, table: str) -> str:
    marker = f"CREATE TABLE [dbo].[{table}]"
    start = sql.index(marker)
    end = sql.find("CREATE TABLE", start + 1)
    return sql[start:] if end < 0 else sql[start:end]


class TestCloseNCRV6(unittest.TestCase):
    def test_root_cause_required(self) -> None:
        self.assertFalse(can_close(None))
        self.assertFalse(can_close(""))
        self.assertFalse(can_close("   "))
        self.assertTrue(can_close("Supplier Raw Material Contamination"))

    def test_csharp_can_close_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn("public static bool CanClose(string rootCauseCategory)", src)
        self.assertIn("return !string.IsNullOrWhiteSpace(rootCauseCategory);", src)
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("QMSNonConformanceRules.CanClose(ncr.RootCauseCategory)", graph)
        self.assertIn("ncr.Status = QMSNonConformanceStatus.Closed;", graph)
        self.assertIn("Root cause category is required before closing the NCR.", graph)


class TestFailPathSeedV6(unittest.TestCase):
    def test_seed_stamps_order_lot_quarantine(self) -> None:
        seeded = seed_from_failed_order("QORD-000001", 42, "LOT-A", 7, "PR000123")
        self.assertEqual(seeded["InspectionOrderNbr"], "QORD-000001")
        self.assertEqual(seeded["InventoryID"], 42)
        self.assertEqual(seeded["LotSerialNbr"], "LOT-A")
        self.assertEqual(seeded["VendorID"], 7)
        self.assertEqual(seeded["ReceiptNbr"], "PR000123")
        self.assertEqual(seeded["Status"], STATUS_OPEN)
        self.assertEqual(seeded["Severity"], SEVERITY_CRITICAL)
        self.assertEqual(seeded["InventoryHoldStatus"], HOLD_QUARANTINE)
        self.assertEqual(seeded["Description"], AUTOMATED_OOS)
        self.assertEqual(seeded["ActionRequired"], QUARANTINE_RTV)

    def test_csharp_seed_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn("public static void SeedFromFailedOrder(", src)
        self.assertIn("ncr.InspectionOrderNbr = inspectionOrderNbr;", src)
        self.assertIn("ncr.InventoryID = inventoryID;", src)
        self.assertIn("ncr.LotSerialNbr = lotSerialNbr;", src)
        self.assertIn("ncr.VendorID = vendorID;", src)
        self.assertIn("ncr.ReceiptNbr = receiptNbr;", src)
        self.assertIn("ncr.Status = QMSNonConformanceStatus.Open;", src)
        self.assertIn("ncr.Severity = QMSSeverity.Critical;", src)
        self.assertIn(
            "ncr.InventoryHoldStatus = QMSInventoryHoldStatus.Quarantine;", src
        )
        self.assertIn(AUTOMATED_OOS, src)
        self.assertIn(QUARANTINE_RTV, src)


class TestNonConformanceDac(unittest.TestCase):
    def test_dac_fields(self) -> None:
        src = DAC_CS.read_text(encoding="utf-8")
        self.assertIn("namespace Lab5.QMS", src)
        self.assertIn("class UsrQMSNonConformance : PXBqlTable, IBqlTable", src)
        self.assertIn("class QMSNonConformance : UsrQMSNonConformance", src)
        self.assertIn("[PXTableName]", src)
        self.assertIn("[PXPrimaryGraph(typeof(QMSNonConformanceEntry))]", src)
        for name in NCR_FIELDS:
            self.assertIn(f"#region {name}", src)
        self.assertIn(
            "[PXSelector(typeof(Search<Users.pKID>), SubstituteKey = typeof(Users.username))]",
            src,
        )

    def test_status_and_severity_constants(self) -> None:
        src = STATUS_CS.read_text(encoding="utf-8")
        self.assertIn(f'public const string Open = "{STATUS_OPEN}"', src)
        self.assertIn(
            f'public const string InInvestigation = "{STATUS_IN_INVESTIGATION}"', src
        )
        self.assertIn(f'public const string Closed = "{STATUS_CLOSED}"', src)
        self.assertIn(f'public const string Void = "{STATUS_VOID}"', src)
        self.assertIn(f'public const string Critical = "{SEVERITY_CRITICAL}"', src)
        self.assertIn(f'public const string Major = "{SEVERITY_MAJOR}"', src)
        self.assertIn(f'public const string Minor = "{SEVERITY_MINOR}"', src)
        self.assertIn(f'public const string Quarantine = "{HOLD_QUARANTINE}"', src)
        self.assertIn(f'public const string Rejected = "{HOLD_REJECTED}"', src)

    def test_sql_synonym_and_columns(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        self.assertIn(
            "CREATE SYNONYM [dbo].[QMSNonConformance] FOR [dbo].[UsrQMSNonConformance]",
            sql,
        )
        block = _table_block(sql, "UsrQMSNonConformance")
        self.assertIn("[UsrQMSNonConformance_PK]", block)
        self.assertIn("[NCRNbr] ASC", block)
        for col in SQL_COLUMNS:
            self.assertIn(f"[{col}]", block)


class TestNonConformanceGraphAndScreen(unittest.TestCase):
    def test_graph_views_and_actions(self) -> None:
        src = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "class QMSNonConformanceEntry : PXGraph<QMSNonConformanceEntry, QMSNonConformance>",
            src,
        )
        self.assertIn(
            "PXSelect<QMSNonConformance,\n            Where<QMSNonConformance.nCRNbr, Equal<Current<QMSNonConformance.nCRNbr>>>> Document",
            src,
        )
        self.assertIn("public PXAction<QMSNonConformance> CloseNCR;", src)
        self.assertIn("public PXAction<QMSNonConformance> DispositionRTV;", src)
        self.assertIn("PXGraph.CreateInstance<POReceiptEntry>()", src)
        self.assertIn(
            'throw new PXRedirectRequiredException(graph, "Return to Vendor");', src
        )
        self.assertIn("Receipt Nbr is required for Return to Vendor.", src)

    def test_screen_qm302000(self) -> None:
        aspx = ASPX.read_text(encoding="utf-8")
        self.assertIn('TypeName="Lab5.QMS.QMSNonConformanceEntry"', aspx)
        self.assertIn('PrimaryView="Document"', aspx)
        self.assertIn('DataMember="Document"', aspx)
        self.assertIn('Name="CloseNCR"', aspx)
        self.assertIn('Name="DispositionRTV"', aspx)
        self.assertIn("QM302000", aspx)
        for field in SUMMARY_FIELDS:
            self.assertIn(f'DataField="{field}"', aspx)


if __name__ == "__main__":
    unittest.main()
