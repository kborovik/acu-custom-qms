"""Read-only preflight: `acu config check` / `show` / `tenant list` vs .env."""

from __future__ import annotations

import unittest

from e2e.helper import instance, run_acu


class TestAcuPreflight(unittest.TestCase):
    def test_config_check_ok_rest_and_endpoints(self) -> None:
        result = run_acu("config", "check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout + result.stderr
        self.assertIn("ok rest", out)
        self.assertIn("ok endpoints", out)
        self.assertNotIn("fail rest", out)

    def test_config_show_redacts_password(self) -> None:
        result = run_acu("config", "show")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout
        self.assertIn("ACU_BASE_URL=", out)
        self.assertIn(f"ACU_TENANT={instance().tenant}", out)
        self.assertNotIn("ACU_PASSWORD=", out)
        self.assertNotRegex(out, r"(?i)password\s*=\s*\S+")

    def test_tenant_list_includes_acu_tenant(self) -> None:
        inst = instance()
        if not inst.ssh:
            self.skipTest("hosted path (blank ACU_SSH) — no tenant list")
        result = run_acu("tenant", "list")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(inst.tenant, result.stdout)


if __name__ == "__main__":
    unittest.main()
