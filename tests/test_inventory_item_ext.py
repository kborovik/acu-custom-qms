#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T2 / V1: InventoryItemExt usr fields for the cannot-pass lot gate."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "InventoryItemExt.cs"
SQL = ROOT / "Scripts" / "CreateQMSTables.sql"

USR_FIELDS = (
    "UsrQMSInspectionRequired",
    "UsrQMSInspectionPlanID",
    "UsrMinShelfLifeDays",
)


class TestInventoryItemExtV1(unittest.TestCase):
    def test_extension_declares_gate_fields(self) -> None:
        src = EXT_CS.read_text(encoding="utf-8")
        self.assertIn("namespace Lab5.QMS", src)
        self.assertIn("class InventoryItemExt : PXCacheExtension<InventoryItem>", src)
        for name in USR_FIELDS:
            self.assertIn("public virtual", src)
            self.assertRegex(src, rf"\b{name}\b")

    def test_inspection_required_defaults_false(self) -> None:
        src = EXT_CS.read_text(encoding="utf-8")
        required = _region(src, "UsrQMSInspectionRequired")
        self.assertIn("[PXDBBool]", required)
        self.assertIn("[PXDefault(false)]", required)
        self.assertIn("bool? UsrQMSInspectionRequired", required)

    def test_plan_id_and_shelf_life_types(self) -> None:
        src = EXT_CS.read_text(encoding="utf-8")
        plan = _region(src, "UsrQMSInspectionPlanID")
        self.assertIn("[PXDBString(30, IsUnicode = true)]", plan)
        self.assertIn("string UsrQMSInspectionPlanID", plan)
        shelf = _region(src, "UsrMinShelfLifeDays")
        self.assertIn("[PXDBInt]", shelf)
        self.assertIn("[PXDefault(0)]", shelf)
        self.assertIn("int? UsrMinShelfLifeDays", shelf)


class TestPatternAStockItemScreen(unittest.TestCase):
    def test_modern_ui_shows_usr_fields(self) -> None:
        base = (
            ROOT
            / "FrontendSources"
            / "screen"
            / "src"
            / "screens"
            / "IN"
            / "IN202500"
            / "extensions"
        )
        html = (base / "IN202500_QMS.html").read_text(encoding="utf-8")
        ts = (base / "IN202500_QMS.ts").read_text(encoding="utf-8")
        for field in USR_FIELDS:
            self.assertIn(f'name="{field}"', html, field)
            self.assertIn(field, ts, field)
        self.assertIn("visible.bind", html)
        self.assertNotIn("if.bind", html)
        self.assertIn("export class InventoryItem", ts)
        self.assertNotIn("InventoryItemExtension", ts)


class TestInventoryItemUsrColumns(unittest.TestCase):
    def test_alter_inventory_item_adds_usr_columns(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        self.assertNotRegex(
            sql,
            r"CREATE TABLE \[dbo\]\.\[InventoryItem\]",
        )
        for col in USR_FIELDS:
            self.assertIn(f"COL_LENGTH(N'dbo.InventoryItem', N'{col}')", sql)
            self.assertRegex(
                sql,
                rf"ALTER TABLE \[dbo\]\.\[InventoryItem\] ADD\s+\[{col}\]",
            )


def _region(src: str, name: str) -> str:
    match = re.search(
        rf"#region {re.escape(name)}\n(.*?)#endregion",
        src,
        flags=re.DOTALL,
    )
    self_msg = f"missing #region {name}"
    if match is None:
        raise AssertionError(self_msg)
    return match.group(1)


if __name__ == "__main__":
    unittest.main()
