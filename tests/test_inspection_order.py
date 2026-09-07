#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T4 / V4: inspection order DACs, QMSInspectionOrderEntry, QM.30.10.00, EvaluateResults."""

from __future__ import annotations

import re
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSInspectionOrder.cs"
RESULT_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSInspectionOrderResult.cs"
STATUS_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSInspectionOrderStatus.cs"
GRAPH_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "QMSInspectionOrderEntry.cs"
RULES_CS = ROOT / "src" / "Lab5.QMS" / "QMSInspectionOrderRules.cs"
ASPX = ROOT / "Pages_QM" / "QM301000.aspx"
SQL = ROOT / "Scripts" / "CreateQMSTables.sql"

LINE_PASS = "P"
LINE_FAIL = "F"
LINE_SKIPPED = "S"
OVERALL_PENDING = "P"
OVERALL_PASS = "V"
OVERALL_FAIL = "F"

ORDER_FIELDS = (
    "InspectionOrderNbr",
    "Status",
    "InventoryID",
    "LotSerialNbr",
    "VendorID",
    "ReceiptNbr",
    "PlanID",
    "TestingLabID",
    "LabCertificateNbr",
    "InspectionDate",
    "OverallEvaluation",
    "EvaluatedByID",
    "EvaluationDateTime",
    "NoteID",
    "CreatedByID",
    "CreatedDateTime",
    "LastModifiedByID",
    "LastModifiedDateTime",
)

RESULT_FIELDS = (
    "InspectionOrderNbr",
    "LineNbr",
    "TestID",
    "TestMethod",
    "TargetSpec",
    "ActualNumericValue",
    "ActualTextValue",
    "Evaluation",
    "Notes",
)

SUMMARY_FIELDS = (
    "InspectionOrderNbr",
    "Status",
    "InventoryID",
    "LotSerialNbr",
    "VendorID",
    "ReceiptNbr",
    "TestingLabID",
    "LabCertificateNbr",
    "OverallEvaluation",
)

GRID_FIELDS = (
    "LineNbr",
    "TestID",
    "TestMethod",
    "TargetSpec",
    "ActualNumericValue",
    "ActualTextValue",
    "Evaluation",
    "Notes",
)


def is_numeric_test(min_value: Decimal | None, max_value: Decimal | None) -> bool:
    return min_value is not None or max_value is not None


def evaluate_numeric(
    actual: Decimal | None,
    min_value: Decimal | None,
    max_value: Decimal | None,
    required: bool,
) -> str:
    if actual is None:
        return LINE_FAIL if required else LINE_SKIPPED
    if min_value is not None and actual < min_value:
        return LINE_FAIL
    if max_value is not None and actual > max_value:
        return LINE_FAIL
    return LINE_PASS


def evaluate_text(actual_text: str | None, required_token: str | None, required: bool) -> str:
    if actual_text is None or actual_text.strip() == "":
        return LINE_FAIL if required else LINE_SKIPPED
    if required_token is None or required_token.strip() == "":
        return LINE_PASS
    return LINE_PASS if required_token.lower() in actual_text.lower() else LINE_FAIL


def evaluate_line(
    min_value: Decimal | None,
    max_value: Decimal | None,
    actual_numeric: Decimal | None,
    actual_text: str | None,
    required_token: str | None,
    required: bool,
) -> str:
    if is_numeric_test(min_value, max_value):
        return evaluate_numeric(actual_numeric, min_value, max_value, required)
    return evaluate_text(actual_text, required_token, required)


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def shelf_life_pass(
    expiry: date | datetime | None,
    receipt: date | datetime | None,
    min_days: int | None,
) -> bool:
    days = 0 if min_days is None else min_days
    if days <= 0:
        return True
    exp = _as_date(expiry)
    rec = _as_date(receipt)
    if exp is None or rec is None:
        return False
    return exp >= rec + timedelta(days=days)


def rollup(any_fail: bool, any_missing_required: bool, shelf_ok: bool) -> str:
    if any_fail or any_missing_required or not shelf_ok:
        return OVERALL_FAIL
    return OVERALL_PASS


def _region(src: str, name: str) -> str:
    match = re.search(
        rf"#region {re.escape(name)}\n(.*?)#endregion",
        src,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing #region {name}")
    return match.group(1)


def _table_block(sql: str, table: str) -> str:
    marker = f"CREATE TABLE [dbo].[{table}]"
    start = sql.index(marker)
    end = sql.find("CREATE TABLE", start + 1)
    return sql[start:] if end < 0 else sql[start:end]


class TestEvaluateNumericV4(unittest.TestCase):
    def test_in_range_pass(self) -> None:
        self.assertEqual(
            evaluate_numeric(Decimal("5"), Decimal("1"), Decimal("10"), True),
            LINE_PASS,
        )

    def test_equal_bounds_pass(self) -> None:
        self.assertEqual(
            evaluate_numeric(Decimal("1"), Decimal("1"), Decimal("1"), True),
            LINE_PASS,
        )

    def test_below_min_fail(self) -> None:
        self.assertEqual(
            evaluate_numeric(Decimal("0.5"), Decimal("1"), Decimal("10"), True),
            LINE_FAIL,
        )

    def test_above_max_fail(self) -> None:
        self.assertEqual(
            evaluate_numeric(Decimal("11"), Decimal("1"), Decimal("10"), True),
            LINE_FAIL,
        )

    def test_nullable_min_only(self) -> None:
        self.assertEqual(evaluate_numeric(Decimal("0"), None, Decimal("10"), True), LINE_PASS)
        self.assertEqual(evaluate_numeric(Decimal("11"), None, Decimal("10"), True), LINE_FAIL)

    def test_nullable_max_only(self) -> None:
        self.assertEqual(evaluate_numeric(Decimal("5"), Decimal("1"), None, True), LINE_PASS)
        self.assertEqual(evaluate_numeric(Decimal("0"), Decimal("1"), None, True), LINE_FAIL)

    def test_missing_required_fail(self) -> None:
        self.assertEqual(evaluate_numeric(None, Decimal("1"), Decimal("10"), True), LINE_FAIL)

    def test_missing_optional_skipped(self) -> None:
        self.assertEqual(evaluate_numeric(None, Decimal("1"), Decimal("10"), False), LINE_SKIPPED)

    def test_csharp_numeric_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static string EvaluateNumeric(decimal? actual, decimal? minValue, decimal? maxValue, bool required)",
            src,
        )
        self.assertIn("if (actual == null)", src)
        self.assertIn("return required ? QMSLineEvaluation.Fail : QMSLineEvaluation.Skipped;", src)
        self.assertIn("actual.Value < minValue.Value", src)
        self.assertIn("actual.Value > maxValue.Value", src)


class TestEvaluateTextV4(unittest.TestCase):
    def test_contains_token_pass(self) -> None:
        self.assertEqual(evaluate_text("Absent in 10g", "Absent", True), LINE_PASS)

    def test_token_case_insensitive(self) -> None:
        self.assertEqual(evaluate_text("ABSENT in 10g", "Absent", True), LINE_PASS)
        self.assertEqual(evaluate_text("negative", "Negative", True), LINE_PASS)

    def test_missing_token_fail(self) -> None:
        self.assertEqual(evaluate_text("Present in 10g", "Absent", True), LINE_FAIL)

    def test_missing_required_text_fail(self) -> None:
        self.assertEqual(evaluate_text(None, "Absent", True), LINE_FAIL)
        self.assertEqual(evaluate_text("  ", "Absent", True), LINE_FAIL)

    def test_missing_optional_text_skipped(self) -> None:
        self.assertEqual(evaluate_text(None, "Absent", False), LINE_SKIPPED)

    def test_empty_token_with_actual_pass(self) -> None:
        self.assertEqual(evaluate_text("clear", None, True), LINE_PASS)

    def test_no_bounds_uses_text_path(self) -> None:
        self.assertEqual(
            evaluate_line(None, None, None, "Absent in 10g", "Absent", True),
            LINE_PASS,
        )
        self.assertEqual(
            evaluate_line(None, None, Decimal("1"), "Present", "Absent", True),
            LINE_FAIL,
        )

    def test_csharp_text_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static string EvaluateText(string actualText, string requiredToken, bool required)",
            src,
        )
        self.assertIn("string.IsNullOrWhiteSpace(actualText)", src)
        self.assertIn("IndexOf(requiredToken, StringComparison.OrdinalIgnoreCase)", src)
        self.assertIn("minValue != null || maxValue != null", src)


class TestShelfLifeV4(unittest.TestCase):
    def test_expiry_meets_min_days(self) -> None:
        receipt = date(2026, 1, 1)
        expiry = date(2026, 4, 1)
        self.assertTrue(shelf_life_pass(expiry, receipt, 90))

    def test_expiry_equal_to_min_days_pass(self) -> None:
        receipt = date(2026, 1, 1)
        expiry = receipt + timedelta(days=30)
        self.assertTrue(shelf_life_pass(expiry, receipt, 30))

    def test_expiry_short_fail(self) -> None:
        receipt = date(2026, 1, 1)
        expiry = date(2026, 1, 10)
        self.assertFalse(shelf_life_pass(expiry, receipt, 30))

    def test_zero_or_null_days_skip(self) -> None:
        self.assertTrue(shelf_life_pass(None, None, 0))
        self.assertTrue(shelf_life_pass(None, None, None))
        self.assertTrue(shelf_life_pass(None, None, -1))

    def test_missing_dates_with_days_fail(self) -> None:
        self.assertFalse(shelf_life_pass(None, date(2026, 1, 1), 10))
        self.assertFalse(shelf_life_pass(date(2026, 6, 1), None, 10))

    def test_csharp_shelf_life_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static bool ShelfLifePass(DateTime? expiryDate, DateTime? receiptDate, int? minShelfLifeDays)",
            src,
        )
        self.assertIn("int days = minShelfLifeDays ?? 0;", src)
        self.assertIn("if (days <= 0)", src)
        self.assertIn("if (expiryDate == null || receiptDate == null)", src)
        self.assertIn("expiryDate.Value.Date >= receiptDate.Value.Date.AddDays(days)", src)


class TestMissingRequiredAndRollupV4(unittest.TestCase):
    def test_all_pass(self) -> None:
        self.assertEqual(rollup(False, False, True), OVERALL_PASS)

    def test_any_line_fail(self) -> None:
        self.assertEqual(rollup(True, False, True), OVERALL_FAIL)

    def test_missing_required(self) -> None:
        self.assertEqual(rollup(False, True, True), OVERALL_FAIL)

    def test_shelf_life_fail_overall(self) -> None:
        self.assertEqual(rollup(False, False, False), OVERALL_FAIL)

    def test_optional_skip_does_not_fail_rollup(self) -> None:
        line = evaluate_numeric(None, Decimal("1"), Decimal("2"), False)
        self.assertEqual(line, LINE_SKIPPED)
        self.assertEqual(rollup(line == LINE_FAIL, False, True), OVERALL_PASS)

    def test_csharp_rollup_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static string Rollup(bool anyFail, bool anyMissingRequired, bool shelfLifePass)",
            src,
        )
        self.assertIn("if (anyFail || anyMissingRequired || !shelfLifePass)", src)
        self.assertIn("return QMSOverallEvaluation.Fail;", src)
        self.assertIn("return QMSOverallEvaluation.Pass;", src)
        status = STATUS_CS.read_text(encoding="utf-8")
        self.assertIn('public const string Pass = "V"', status)
        self.assertIn('public const string Fail = "F"', status)
        self.assertIn('public const string Pending = "P"', status)
        self.assertIn('public const string Skipped = "S"', status)


class TestInspectionOrderDac(unittest.TestCase):
    def test_order_dac_fields(self) -> None:
        src = ORDER_CS.read_text(encoding="utf-8")
        self.assertIn("namespace Lab5.QMS", src)
        self.assertIn("class UsrQMSInspectionOrder : PXBqlTable, IBqlTable", src)
        self.assertIn("class QMSInspectionOrder : UsrQMSInspectionOrder", src)
        self.assertIn("[PXTableName]", src)
        for name in ORDER_FIELDS:
            self.assertIn(f"#region {name}", src)

    def test_result_dac_fields(self) -> None:
        src = RESULT_CS.read_text(encoding="utf-8")
        self.assertIn("class UsrQMSInspectionOrderResult : PXBqlTable, IBqlTable", src)
        self.assertIn("class QMSInspectionOrderResult : UsrQMSInspectionOrderResult", src)
        self.assertIn("[PXTableName]", src)
        for name in RESULT_FIELDS:
            self.assertIn(f"#region {name}", src)

    def test_status_open_constant(self) -> None:
        src = STATUS_CS.read_text(encoding="utf-8")
        self.assertIn('public const string Open = "O"', src)
        self.assertIn('public const string Completed = "C"', src)
        self.assertIn('public const string Cancelled = "X"', src)

    def test_sql_synonyms_bind_dac_names(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        self.assertIn(
            "CREATE SYNONYM [dbo].[QMSInspectionOrder] FOR [dbo].[UsrQMSInspectionOrder]",
            sql,
        )
        self.assertIn(
            "CREATE SYNONYM [dbo].[QMSInspectionOrderResult] FOR [dbo].[UsrQMSInspectionOrderResult]",
            sql,
        )
        block = _table_block(sql, "UsrQMSInspectionOrder")
        self.assertIn("[UsrQMSInspectionOrder_PK]", block)
        self.assertIn("[InspectionOrderNbr] ASC", block)


class TestInspectionOrderGraphAndScreen(unittest.TestCase):
    def test_graph_views_and_evaluate(self) -> None:
        src = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "class QMSInspectionOrderEntry : PXGraph<QMSInspectionOrderEntry, QMSInspectionOrder>",
            src,
        )
        self.assertIn(
            "PXSelect<QMSInspectionOrder,\n            Where<QMSInspectionOrder.inspectionOrderNbr, Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>>> Document",
            src,
        )
        self.assertIn(
            "PXSelect<QMSInspectionOrderResult,\n            Where<QMSInspectionOrderResult.inspectionOrderNbr, Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>>> Results",
            src,
        )
        self.assertIn("public PXAction<QMSInspectionOrder> EvaluateResults;", src)
        self.assertIn("QMSInspectionOrderRules.EvaluateLine", src)
        self.assertIn("QMSInspectionOrderRules.ShelfLifePass", src)
        self.assertIn("QMSInspectionOrderRules.Rollup", src)
        self.assertIn("ext.UsrMinShelfLifeDays", src)
        self.assertIn("receipt.ReceiptDate", src)
        self.assertIn("lot.ExpireDate", src)

    def test_screen_qm301000(self) -> None:
        aspx = ASPX.read_text(encoding="utf-8")
        self.assertIn('TypeName="Lab5.QMS.QMSInspectionOrderEntry"', aspx)
        self.assertIn('PrimaryView="Document"', aspx)
        self.assertIn('DataMember="Document"', aspx)
        self.assertIn('DataMember="Results"', aspx)
        self.assertIn('Name="EvaluateResults"', aspx)
        for field in SUMMARY_FIELDS:
            self.assertIn(f'DataField="{field}"', aspx)
        for field in GRID_FIELDS:
            self.assertIn(f'DataField="{field}"', aspx)


if __name__ == "__main__":
    unittest.main()
