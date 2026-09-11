#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T46 / V21: tracked *.py git mode 100755 iff shebang."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NO_SHEBANG = frozenset({"e2e/helper.py", "e2e/__init__.py"})


def _tracked_py() -> list[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-s", "-z", "--", "*.py"],
        check=True,
        capture_output=True,
    )
    rows: list[tuple[str, str]] = []
    for entry in proc.stdout.decode().split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        mode = meta.split(" ", 1)[0]
        rows.append((path, mode))
    return rows


def _has_shebang(path: str) -> bool:
    text = (ROOT / path).read_text(encoding="utf-8")
    first = text.splitlines()[0] if text else ""
    return first.startswith("#!")


class TestPyShebangExecV21(unittest.TestCase):
    def test_tracked_py_git_mode_matches_shebang(self) -> None:
        rows = _tracked_py()
        self.assertTrue(rows, "git ls-files returned no *.py")
        modes = {mode for _, mode in rows}
        self.assertIn("100755", modes)
        self.assertIn("100644", modes)
        for path, mode in rows:
            expected = "100755" if _has_shebang(path) else "100644"
            self.assertEqual(mode, expected, path)

    def test_library_py_have_no_shebang(self) -> None:
        for path, _mode in _tracked_py():
            if path.startswith("acuqms/") or path in NO_SHEBANG:
                self.assertFalse(_has_shebang(path), path)


if __name__ == "__main__":
    unittest.main()
