#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""e2e hang bounds: HTTP / acu / 202-poll / process timeout (gmake e2e)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestE2eTimeouts(unittest.TestCase):
    def test_helper_bounds_http_acu_and_invoke(self) -> None:
        src = (ROOT / "e2e" / "helper.py").read_text(encoding="utf-8")
        publish = (ROOT / "lab5_qms" / "publish.py").read_text(encoding="utf-8")
        acu = (ROOT / "lab5_qms" / "acu.py").read_text(encoding="utf-8")
        self.assertIn("HTTP_TIMEOUT = 30.0", acu)
        self.assertIn("ACU_TIMEOUT = 60.0", src)
        self.assertIn("INVOKE_TIMEOUT = 60.0", src)
        self.assertIn("SSH_TIMEOUT = 30.0", acu)
        self.assertIn("sqlcmd via ssh timed out", publish)
        self.assertIn("timeout: float = HTTP_TIMEOUT", acu)
        self.assertIn("timeout: float = ACU_TIMEOUT", src)
        self.assertIn("timeout: float = INVOKE_TIMEOUT", src)
        self.assertIn("timeout=timeout", src)
        self.assertIn("did not complete within", src)
        self.assertIn("did not complete within", publish)
        self.assertIn("faulthandler.dump_traceback_later", src)
        self.assertIn("E2E_TIMEOUT", src)
        self.assertNotIn("timeout: float = 300.0", src)
        self.assertNotIn("timeout: float = 300.0", publish)
        self.assertNotIn("timeout: float = 300.0", acu)

    def test_makefile_unbuffered_e2e_timeout(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("PYTHONUNBUFFERED := 1", makefile)
        self.assertIn("E2E_TIMEOUT ?= 900", makefile)
        self.assertIn("python -u -m unittest discover -s tests", makefile)
        self.assertIn("python -u -m unittest discover -s e2e -t . -v", makefile)
        self.assertNotIn("$(UV) run python -m unittest discover", makefile)


if __name__ == "__main__":
    unittest.main()
