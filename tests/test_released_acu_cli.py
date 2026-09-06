#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T17 / T18 / V11: project must not declare or import acumatica-cli."""

from __future__ import annotations

import os
import sys
import tomllib
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lab5_qms.acu import (  # noqa: E402
    load_instance,
    parse_env_lines,
    parse_tenant_list,
    unwrap,
    wrap,
)


def _py_sources() -> list[Path]:
    files = list((ROOT / "lab5_qms").rglob("*.py"))
    files.append(ROOT / "dll.py")
    files.extend(p for p in (ROOT / "e2e").glob("*.py"))
    return files


class TestProjectOmitsAcumaticaCliV11(unittest.TestCase):
    def test_pyproject_deps_and_uv_sources_omit_acumatica_cli(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("acumatica-cli", text)
        data = tomllib.loads(text)
        deps = data["project"]["dependencies"]
        self.assertTrue(all("acumatica-cli" not in dep for dep in deps))
        sources = data.get("tool", {}).get("uv", {}).get("sources", {})
        self.assertNotIn("acumatica-cli", sources)
        self.assertTrue(any("httpx" in dep for dep in deps))

    def test_uv_lock_omits_acumatica_cli(self) -> None:
        text = (ROOT / "uv.lock").read_text(encoding="utf-8")
        self.assertNotIn('name = "acumatica-cli"', text)
        self.assertNotIn("kborovik/acumatica-cli", text)


class TestPathAcuNotImportV11(unittest.TestCase):
    def test_lab5_qms_dll_e2e_do_not_import_acumatica_cli(self) -> None:
        for path in _py_sources():
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(
                text, r"(?m)^\s*import acumatica_cli\b", path.name
            )
            self.assertNotRegex(
                text, r"(?m)^\s*from acumatica_cli\b", path.name
            )
            self.assertNotIn('["uv", "run", "acu"]', text, path.name)
            self.assertNotIn("uv run -- acu", text, path.name)

    def test_acu_module_invokes_path_acu(self) -> None:
        src = (ROOT / "lab5_qms" / "acu.py").read_text(encoding="utf-8")
        self.assertIn('["acu", *args]', src)
        self.assertIn('run_acu("config", "show")', src)
        self.assertIn('run_acu("tenant", "list")', src)
        self.assertIn("uv tool install acumatica-cli", src)
        self.assertNotIn('["uv", "run", "acu"]', src)
        self.assertNotIn("print(inst.password", src)
        self.assertNotIn("print(password", src)

    def test_dll_uses_path_acu_not_tenant_manager(self) -> None:
        src = (ROOT / "dll.py").read_text(encoding="utf-8")
        self.assertIn("from lab5_qms.acu import", src)
        self.assertIn("load_instance", src)
        self.assertIn("ssh_run", src)
        self.assertNotIn("TenantManager", src)
        self.assertNotIn("acumatica_cli", src)

    def test_wrap_unwrap_contract_values(self) -> None:
        wrapped = wrap(
            {"PlanID": "X", "Tests": [{"LineNbr": 10, "id": "keep"}]}
        )
        self.assertEqual(wrapped["PlanID"], {"value": "X"})
        self.assertEqual(wrapped["Tests"][0]["LineNbr"], {"value": 10})
        self.assertEqual(wrapped["Tests"][0]["id"], "keep")
        plain = unwrap(
            {
                "PlanID": {"value": "X"},
                "Tests": [{"LineNbr": {"value": 10}, "id": "keep"}],
            }
        )
        self.assertEqual(plain["PlanID"], "X")
        self.assertEqual(plain["Tests"][0]["LineNbr"], 10)

    def test_parse_env_lines_drops_password(self) -> None:
        fields = parse_env_lines(
            "# resolved\n"
            "ACU_BASE_URL=http://erp.test/AcumaticaERP\n"
            "ACU_SSH=Administrator@erp.test\n"
            "ACU_TENANT=DEV\n"
            "ACU_PASSWORD=secret\n"
        )
        self.assertEqual(fields["ACU_BASE_URL"], "http://erp.test/AcumaticaERP")
        self.assertEqual(fields["ACU_TENANT"], "DEV")
        self.assertNotIn("ACU_PASSWORD", fields)

    def test_parse_tenant_list_rows(self) -> None:
        tenants = parse_tenant_list(
            "Tenants on erp.test\n"
            " ID  Login   CD       Type\n"
            "  1  SYSTEM  COMPANY\n"
            " 14  DEV     DEV      SalesDemo\n"
        )
        self.assertEqual(tenants[0].company_id, 1)
        self.assertEqual(tenants[0].login_name, "SYSTEM")
        self.assertEqual(tenants[1].company_id, 14)
        self.assertEqual(tenants[1].login_name, "DEV")
        self.assertEqual(tenants[1].company_type, "SalesDemo")

    def test_load_instance_uses_acu_config_show(self) -> None:
        show = (
            "ACU_BASE_URL=http://erp.test/AcumaticaERP\n"
            "ACU_SSH=Administrator@erp.test\n"
            "ACU_TENANT=DEV\n"
            "ACU_API_VERSION=25.200.001\n"
            "ACU_USER=admin\n"
        )
        fake = CompletedProcess(["acu", "config", "show"], 0, show, "")
        with (
            patch("lab5_qms.acu.run_acu", return_value=fake) as run,
            patch.dict(os.environ, {"ACU_PASSWORD": "secret"}, clear=False),
        ):
            inst = load_instance()
        run.assert_called_once_with("config", "show")
        self.assertEqual(inst.base_url, "http://erp.test/AcumaticaERP")
        self.assertEqual(inst.ssh, "Administrator@erp.test")
        self.assertEqual(inst.tenant, "DEV")
        self.assertEqual(inst.password, "secret")
        self.assertNotIn("secret", repr(inst))


class TestPreflightPathAcuV11(unittest.TestCase):
    def test_makefile_preflight_uses_path_acu(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("acu config check", makefile)
        self.assertIn("uv tool install acumatica-cli", makefile)
        self.assertNotIn("$(UV) run acu", makefile)
        self.assertNotIn("uv run acu config", makefile)

    def test_agents_and_readme_use_path_acu(self) -> None:
        for name in ("AGENTS.md", "README.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("acu config check", text, name)
            self.assertIn("uv tool install acumatica-cli", text, name)
            self.assertNotIn("uv run acu config", text, name)
            self.assertNotIn("$(UV) run acu", text, name)


if __name__ == "__main__":
    unittest.main()
