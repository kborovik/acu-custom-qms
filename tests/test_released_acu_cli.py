#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T17 / V11: project must not declare acumatica-cli."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestProjectOmitsAcumaticaCliV11(unittest.TestCase):
    def test_pyproject_deps_and_uv_sources_omit_acumatica_cli(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("acumatica-cli", text)
        data = tomllib.loads(text)
        deps = data["project"]["dependencies"]
        self.assertTrue(all("acumatica-cli" not in dep for dep in deps))
        sources = data.get("tool", {}).get("uv", {}).get("sources", {})
        self.assertNotIn("acumatica-cli", sources)

    def test_uv_lock_omits_acumatica_cli(self) -> None:
        text = (ROOT / "uv.lock").read_text(encoding="utf-8")
        self.assertNotIn('name = "acumatica-cli"', text)
        self.assertNotIn("kborovik/acumatica-cli", text)


if __name__ == "__main__":
    unittest.main()
