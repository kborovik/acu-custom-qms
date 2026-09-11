#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T49 / V17 / I.pkg: tests Path-literal screen prefix → FRONTEND_SCREENS_REL."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acuqms.paths import FRONTEND_SCREENS_REL  # noqa: E402

_PIECEWISE = re.compile(
    r'["\']QMS["\']\s*/\s*["\']FrontendSources["\']\s*/\s*'
    r'["\']screen["\']\s*/\s*["\']src["\']\s*/\s*'
    r'["\']development["\']\s*/\s*["\']screens["\']',
    re.DOTALL,
)


class TestFrontendScreensRelT49(unittest.TestCase):
    def test_tests_import_constant_not_path_literal(self) -> None:
        needle = FRONTEND_SCREENS_REL.as_posix()
        posix_path = re.compile(
            rf"""(?:Path\s*\(\s*|/\s*)["']{re.escape(needle)}["']"""
        )
        rows = list((ROOT / "tests").rglob("test_*.py"))
        self.assertTrue(rows, "no tests/test_*.py")
        for path in rows:
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(ROOT).as_posix()
            self.assertIsNone(_PIECEWISE.search(text), rel)
            self.assertIsNone(posix_path.search(text), rel)


if __name__ == "__main__":
    unittest.main()
