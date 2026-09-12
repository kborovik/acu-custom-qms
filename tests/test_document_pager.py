#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T52 / V22 / B14: QM document Document PXSelect is unfiltered so Next lands a sibling."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GRAPH_DIR = ROOT / "QMS" / "Lab5.QMS" / "Graph"
E2E = ROOT / "e2e" / "test_document_pager.py"

ORDER_CS = GRAPH_DIR / "QMSInspectionOrderEntry.cs"
PLAN_CS = GRAPH_DIR / "QMSInspectionPlanMaint.cs"
NCR_CS = GRAPH_DIR / "QMSNonConformanceEntry.cs"


def _view_decl(src: str, view: str) -> str:
    match = re.search(
        rf"public PXSelect<(.*?)>\s+{re.escape(view)};",
        src,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing PXSelect {view}")
    return match.group(1)


class TestV22_DocumentPagerNextLandsSibling(unittest.TestCase):
    """V22 / B14: Document ! Current-key Where; detail views keep it."""

    def test_order_document_unfiltered_results_current(self) -> None:
        src = ORDER_CS.read_text(encoding="utf-8")
        document = _view_decl(src, "Document")
        self.assertEqual(document.strip(), "QMSInspectionOrder")
        self.assertNotIn("Equal<Current<", document)
        results = _view_decl(src, "Results")
        self.assertIn(
            "Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>",
            results,
        )

    def test_plan_document_unfiltered_tests_current(self) -> None:
        src = PLAN_CS.read_text(encoding="utf-8")
        document = _view_decl(src, "Document")
        self.assertEqual(document.strip(), "QMSInspectionPlan")
        self.assertNotIn("Equal<Current<", document)
        tests = _view_decl(src, "Tests")
        self.assertIn("Equal<Current<QMSInspectionPlan.planID>>", tests)

    def test_ncr_document_unfiltered(self) -> None:
        src = NCR_CS.read_text(encoding="utf-8")
        document = _view_decl(src, "Document")
        self.assertEqual(document.strip(), "QMSNonConformance")
        self.assertNotIn("Equal<Current<", document)

    def test_e2e_qm301000_next_from_named_order(self) -> None:
        src = E2E.read_text(encoding="utf-8")
        self.assertIn("class TestDocumentPagerV22", src)
        self.assertIn("test_qm301000_next_from_named_order_lands_next_nbr", src)
        self.assertIn("FAIL_ORDER", src)
        self.assertIn("InspectionOrderNbr", src)
        self.assertIn("$orderby", src)
        self.assertIn("ScreenId", src)
        self.assertIn("QM301000", src)


if __name__ == "__main__":
    unittest.main()
