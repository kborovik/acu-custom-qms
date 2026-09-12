#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T56 / V25: PXUIField DisplayName is PascalCase with no space."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CS_ROOT = ROOT / "QMS" / "Lab5.QMS"
TESTS_ROOT = ROOT / "tests"
ENDPOINT_XML = ROOT / "QMS" / "_project" / "QMS.xml"

DISPLAY_RE = re.compile("DisplayName" + r' = "([^"]*)"')
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
REGION_RE = re.compile(
    r"#region (?P<member>\w+)\n(?P<body>.*?)#endregion",
    flags=re.DOTALL,
)

QUALIFIED = {
    ("QMSInspectionOrder.cs", "ReceiptNbr"): "PurchaseReceipt",
    ("QMSInspectionOrder.cs", "PlanID"): "InspectionPlan",
    ("QMSNonConformance.cs", "ReceiptNbr"): "PurchaseReceipt",
    ("InventoryItemExt.cs", "UsrQMSInspectionPlanID"): "InspectionPlan",
}

ACTION_NAMES = {
    "QMSInspectionOrderEntry.cs": ("EvaluateResults", "ReleaseLotDecision"),
    "QMSNonConformanceEntry.cs": ("CloseNCR", "DispositionRTV"),
}


def _hits(path: Path) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for match in DISPLAY_RE.finditer(line):
            rows.append((i, match.group(1)))
    return rows


def _scope_files() -> list[Path]:
    files = list(CS_ROOT.rglob("*.cs")) + list(TESTS_ROOT.glob("test_*.py"))
    return sorted(p for p in files if p.is_file())


class TestV25_DisplayNamePascal(unittest.TestCase):
    """V25: DisplayName PascalCase ! space slash period hyphen; REST names stay."""

    def test_display_name_no_space(self) -> None:
        scoped = _scope_files()
        self.assertTrue(any(p.suffix == ".cs" for p in scoped))
        self.assertTrue(any(p.suffix == ".py" for p in scoped))
        found = 0
        for path in scoped:
            for line_no, value in _hits(path):
                found += 1
                loc = f"{path.relative_to(ROOT)}:{line_no}"
                self.assertRegex(value, PASCAL_RE, loc)
                self.assertNotRegex(value, r"[\s/.\-]", loc)
        self.assertGreater(found, 50)

    def test_default_member_name_or_qualified(self) -> None:
        for path in sorted(CS_ROOT.rglob("*.cs")):
            src = path.read_text(encoding="utf-8")
            name = path.name
            for match in REGION_RE.finditer(src):
                body = match.group("body")
                values = DISPLAY_RE.findall(body)
                if not values:
                    continue
                member = match.group("member")
                expected = QUALIFIED.get((name, member), member)
                self.assertEqual(values[0], expected, f"{name}#{member}")
                if member == "LineNbr":
                    self.assertIn("Visible = false", body, f"{name}#LineNbr")

    def test_action_display_names_match_members(self) -> None:
        graph = CS_ROOT / "Graph"
        for filename, members in ACTION_NAMES.items():
            values = [v for _, v in _hits(graph / filename)]
            self.assertEqual(sorted(values), sorted(members), filename)

    def test_rest_field_names_stay(self) -> None:
        xml = ENDPOINT_XML.read_text(encoding="utf-8")
        self.assertIn('<Field name="ReceiptNbr" type="StringValue" />', xml)
        self.assertIn('<Field name="PlanID" type="StringValue" />', xml)
        self.assertIn('<Field name="LineNbr" type="IntValue" />', xml)
        self.assertNotIn('<Field name="PurchaseReceipt"', xml)
        self.assertNotIn('<Field name="InspectionPlan"', xml)


if __name__ == "__main__":
    unittest.main()
