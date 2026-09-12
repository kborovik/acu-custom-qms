#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T3 / V7: inspection plan DACs, QMSInspectionPlanMaint, QM.20.10.00."""

from __future__ import annotations

import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acuqms.paths import FRONTEND_SCREENS_REL  # noqa: E402

PLAN_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionPlan.cs"
TEST_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionPlanTest.cs"
STATUS_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionPlanStatus.cs"
GRAPH_CS = ROOT / "QMS" / "Lab5.QMS" / "Graph" / "QMSInspectionPlanMaint.cs"
RULES_CS = ROOT / "QMS" / "Lab5.QMS" / "QMSInspectionPlanRules.cs"
HTML = ROOT / FRONTEND_SCREENS_REL / "QM" / "QM201000" / "QM201000.html"
TS = ROOT / FRONTEND_SCREENS_REL / "QM" / "QM201000" / "QM201000.ts"
SQL = ROOT / "QMS" / "SQL" / "CreateQMSTables.sql"

PLAN_FIELDS = (
    "PlanID",
    "Description",
    "InventoryID",
    "SamplingPlan",
    "Status",
    "RevisionID",
    "EffectiveDate",
    "NoteID",
    "CreatedByID",
    "CreatedDateTime",
    "LastModifiedByID",
    "LastModifiedDateTime",
)

TEST_FIELDS = (
    "PlanID",
    "LineNbr",
    "TestID",
    "Description",
    "TestMethod",
    "TargetValue",
    "MinValue",
    "MaxValue",
    "UOM",
    "Criticality",
    "IsRequired",
)

SUMMARY_FIELDS = (
    "PlanID",
    "Description",
    "InventoryID",
    "SamplingPlan",
    "Status",
    "EffectiveDate",
)

GRID_FIELDS = (
    "LineNbr",
    "TestID",
    "Description",
    "TestMethod",
    "TargetValue",
    "MinValue",
    "MaxValue",
    "UOM",
    "Criticality",
)


def bounds_valid(min_value: Decimal | None, max_value: Decimal | None) -> bool:
    if min_value is None or max_value is None:
        return True
    return min_value <= max_value


def normalize_plan_id(plan_id: str | None) -> str | None:
    return None if plan_id is None else plan_id.upper()


def _region(src: str, name: str) -> str:
    match = re.search(
        rf"#region {re.escape(name)}\n(.*?)#endregion",
        src,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing #region {name}")
    return match.group(1)


class TestPlanBoundsV7(unittest.TestCase):
    def test_both_set_min_le_max_ok(self) -> None:
        self.assertTrue(bounds_valid(Decimal("1"), Decimal("2")))
        self.assertTrue(bounds_valid(Decimal("5"), Decimal("5")))

    def test_both_set_min_gt_max_fail(self) -> None:
        self.assertFalse(bounds_valid(Decimal("3"), Decimal("1")))

    def test_nullable_bound_ok(self) -> None:
        self.assertTrue(bounds_valid(None, Decimal("1")))
        self.assertTrue(bounds_valid(Decimal("1"), None))
        self.assertTrue(bounds_valid(None, None))

    def test_csharp_bounds_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static bool BoundsValid(decimal? minValue, decimal? maxValue)", src
        )
        self.assertIn("if (minValue == null || maxValue == null)", src)
        self.assertIn("return minValue.Value <= maxValue.Value;", src)

    def test_graph_blocks_invalid_bounds(self) -> None:
        src = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "QMSInspectionPlanRules.BoundsValid(row.MinValue, row.MaxValue)", src
        )
        self.assertIn("PXRowPersistingException", src)
        self.assertIn("MinValue must be less than or equal to MaxValue.", src)


class TestPlanIdUniqueUppercaseV7(unittest.TestCase):
    def test_normalize_plan_id_uppercase(self) -> None:
        self.assertEqual(normalize_plan_id("qplan-bot-ech4"), "QPLAN-BOT-ECH4")
        self.assertEqual(normalize_plan_id("QPLAN-BOT-ECH4"), "QPLAN-BOT-ECH4")
        self.assertIsNone(normalize_plan_id(None))

    def test_csharp_normalize_and_key(self) -> None:
        rules = RULES_CS.read_text(encoding="utf-8")
        self.assertIn("planID.ToUpperInvariant()", rules)
        plan = PLAN_CS.read_text(encoding="utf-8")
        region = _region(plan, "PlanID")
        self.assertIn("IsKey = true", region)
        self.assertIn('InputMask = ">CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"', region)
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("QMSInspectionPlanRules.NormalizePlanID", graph)

    def test_sql_planid_unique_pk(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        block = _table_block(sql, "UsrQMSInspectionPlan")
        self.assertIn("[UsrQMSInspectionPlan_PK]", block)
        self.assertIn("[PlanID] ASC", block)


class TestInspectionPlanDac(unittest.TestCase):
    def test_plan_dac_fields(self) -> None:
        src = PLAN_CS.read_text(encoding="utf-8")
        self.assertIn("namespace Lab5.QMS", src)
        self.assertIn("class UsrQMSInspectionPlan : PXBqlTable, IBqlTable", src)
        self.assertIn("class QMSInspectionPlan : UsrQMSInspectionPlan", src)
        self.assertIn("[PXTableName]", src)
        self.assertIn("ValidateValue = false", src)
        for name in PLAN_FIELDS:
            self.assertIn(f"#region {name}", src)

    def test_plan_test_dac_fields(self) -> None:
        src = TEST_CS.read_text(encoding="utf-8")
        self.assertIn("class UsrQMSInspectionPlanTest : PXBqlTable, IBqlTable", src)
        self.assertIn("class QMSInspectionPlanTest : UsrQMSInspectionPlanTest", src)
        self.assertIn("[PXTableName]", src)
        line_nbr = src[
            src.index("#region LineNbr") : src.index(
                "#endregion", src.index("#region LineNbr")
            )
        ]
        self.assertNotIn("Enabled = false", line_nbr)
        for name in TEST_FIELDS:
            self.assertIn(f"#region {name}", src)

    def test_status_active_constant(self) -> None:
        src = STATUS_CS.read_text(encoding="utf-8")
        self.assertIn('public const string Active = "A"', src)
        self.assertIn("public class active :", src)

    def test_sql_synonyms_bind_dac_names(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        self.assertIn(
            "CREATE SYNONYM [dbo].[QMSInspectionPlan] FOR [dbo].[UsrQMSInspectionPlan]",
            sql,
        )
        self.assertIn(
            "CREATE SYNONYM [dbo].[QMSInspectionPlanTest] FOR [dbo].[UsrQMSInspectionPlanTest]",
            sql,
        )


class TestInspectionPlanGraphAndScreen(unittest.TestCase):
    def test_graph_views(self) -> None:
        src = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "class QMSInspectionPlanMaint : PXGraph<QMSInspectionPlanMaint, QMSInspectionPlan>",
            src,
        )
        self.assertIn("FindPersistedTest", src)
        self.assertIn("e.Cancel = true", src)
        self.assertIn("CopyPendingTestFields", src)
        self.assertIn("QMSInspectionPlanTest.isRequired", src)
        self.assertIn("GetValuePending", src)
        self.assertIn("PXSelect<QMSInspectionPlan> Document", src)
        self.assertIn(
            "PXSelect<QMSInspectionPlanTest,\n            Where<QMSInspectionPlanTest.planID, Equal<Current<QMSInspectionPlan.planID>>>,\n            OrderBy<Asc<QMSInspectionPlanTest.lineNbr>>> Tests",
            src,
        )

    def test_screen_qm201000(self) -> None:
        html = HTML.read_text(encoding="utf-8")
        ts = TS.read_text(encoding="utf-8")
        self.assertIn("export class QM201000 extends PXScreen", ts)
        self.assertIn('graphType: "Lab5.QMS.QMSInspectionPlanMaint"', ts)
        self.assertIn('primaryView: "Document"', ts)
        self.assertIn("Document = createSingle", ts)
        self.assertIn("Tests = createCollection", ts)
        self.assertIn('view.bind="Document"', html)
        self.assertIn('view.bind="Tests"', html)
        for field in SUMMARY_FIELDS:
            self.assertIn(f'name="{field}"', html)
        for field in GRID_FIELDS:
            self.assertIn(field, ts)


def _table_block(sql: str, table: str) -> str:
    marker = f"CREATE TABLE [dbo].[{table}]"
    start = sql.index(marker)
    end = sql.find("CREATE TABLE", start + 1)
    return sql[start:] if end < 0 else sql[start:end]


if __name__ == "__main__":
    unittest.main()
