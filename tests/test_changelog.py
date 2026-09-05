#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Scripts/changelog — Keep-a-Changelog promote / notes / empty hard-fail.

Offline only: fixture CHANGELOG via CHANGELOG_PATH. Makefile wiring is
asserted as a source contract (no live tag push).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "Scripts" / "changelog"
MAKEFILE = ROOT / "Makefile"

SAMPLE = """\
# Changelog

## Unreleased

### Added

- **Ship feature:** does the thing.

### Fixed

- Typo in help.

## [v0.1.0] - 2026-01-01

### Added

- First cut.
"""

EMPTY_UNRELEASED = """\
# Changelog

## Unreleased

## [v0.1.0] - 2026-01-01

### Added

- First cut.
"""


def _run(*args: str, changelog: Path, check: bool = False) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["CHANGELOG_PATH"] = str(changelog)
    return subprocess.run(
        [str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=check,
    )


class TestChangelogScript(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "CHANGELOG.md"
        self.path.write_text(SAMPLE)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_check_ok_when_bullets(self) -> None:
        r = _run("check", changelog=self.path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok", r.stdout)

    def test_check_fails_when_empty_unreleased(self) -> None:
        self.path.write_text(EMPTY_UNRELEASED)
        r = _run("check", changelog=self.path)
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing to ship", r.stderr)

    def test_promote_moves_body_leaves_empty_unreleased(self) -> None:
        r = _run("promote", "0.2.0", "2026-07-30", changelog=self.path)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = self.path.read_text()
        self.assertLess(text.index("## Unreleased"), text.index("## [v0.2.0] - 2026-07-30"))
        self.assertLess(text.index("## [v0.2.0] - 2026-07-30"), text.index("## [v0.1.0]"))
        after = text.split("## Unreleased", 1)[1]
        before_next = after.split("## [", 1)[0]
        self.assertNotIn("- ", before_next)
        self.assertIn("Ship feature", text.split("## [v0.2.0]", 1)[1])
        self.assertIn("First cut", text.split("## [v0.1.0]", 1)[1])

    def test_promote_empty_fails_no_write(self) -> None:
        self.path.write_text(EMPTY_UNRELEASED)
        before = self.path.read_text()
        r = _run("promote", "0.2.0", "2026-07-30", changelog=self.path)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.path.read_text(), before)

    def test_notes_extracts_version_section(self) -> None:
        r = _run("notes", "0.1.0", changelog=self.path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("First cut", r.stdout)
        self.assertNotIn("Ship feature", r.stdout)
        self.assertNotIn("## [", r.stdout)

    def test_notes_accepts_tag_form(self) -> None:
        r = _run("notes", "v0.1.0", changelog=self.path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("First cut", r.stdout)

    def test_notes_after_promote(self) -> None:
        self.assertEqual(
            _run("promote", "0.2.0", "2026-07-30", changelog=self.path).returncode,
            0,
        )
        r = _run("notes", "v0.2.0", changelog=self.path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Ship feature", r.stdout)
        self.assertIn("Typo in help", r.stdout)
        self.assertNotIn("First cut", r.stdout)


class TestMakefileRelease(unittest.TestCase):
    def test_makefile_release_uses_changelog_and_gh(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("Scripts/changelog check", text)
        self.assertIn("Scripts/changelog promote", text)
        self.assertIn("Scripts/changelog notes", text)
        self.assertIn("version --bump", text)
        self.assertIn("gh release create", text)
        self.assertIn("--verify-tag", text)
        self.assertIn("Lab5_QMS_Customization.zip", text)
        self.assertIn("git tag", text)


if __name__ == "__main__":
    unittest.main()
