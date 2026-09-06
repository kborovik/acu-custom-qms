#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T14 / I.cmd / V8 / V10: Click console script lab5-qms pack+publish+seed."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lab5_qms.cli import cli  # noqa: E402
from lab5_qms.publish import seed_qm_rights  # noqa: E402


class TestProjectScriptsICmd(unittest.TestCase):
    def test_pyproject_wires_lab5_qms_console_script(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[project.scripts]", text)
        self.assertIn('lab5-qms = "lab5_qms.cli:main"', text)
        self.assertIn("[build-system]", text)
        self.assertIn("click>=8.1", text)

    def test_makefile_pack_uses_lab5_qms(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("lab5-qms pack", makefile)
        self.assertNotIn("./pack.py", makefile)


class TestCliHelpICmd(unittest.TestCase):
    def test_help_lists_pack_publish_seed(self) -> None:
        r = CliRunner().invoke(cli, ["--help"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertIn("pack", r.output)
        self.assertIn("publish", r.output)
        self.assertIn("seed", r.output)
        self.assertIn("Lab5_QMS_Customization.zip", r.output)
        self.assertIn("CustomizationApi", r.output)
        self.assertIn("Quality Manager", r.output)


class TestCliPackV8(unittest.TestCase):
    def test_pack_writes_zip_without_role_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            r = CliRunner().invoke(cli, ["pack", "-o", str(dest)])
            self.assertEqual(r.exit_code, 0, r.output)
            self.assertTrue(dest.is_file())
            with zipfile.ZipFile(dest) as zf:
                names = set(zf.namelist())
                project = zf.read("project.xml").decode("utf-8")
                sql = zf.read("Scripts/CreateQMSTables.sql").decode("utf-8")
            blob = project + sql + " ".join(names)
            self.assertIn("project.xml", names)
            self.assertIn("_project/ProjectMetadata.xml", names)
            self.assertIn("Scripts/CreateQMSTables.sql", names)
            for token in ("RolesInGraph", "UsersInRoles"):
                self.assertNotIn(token, blob, token)
            self.assertNotIn("<Role", project)
            self.assertNotIn("Quality Manager", blob)


class TestCliDeployPipelineICmd(unittest.TestCase):
    def test_default_packs_publishes_and_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            dest.write_bytes(b"PK\x03\x04fake")
            session = object()
            ctx = MagicMock()
            ctx.__enter__.return_value = session
            ctx.__exit__.return_value = None
            with (
                patch("lab5_qms.cli.pack.write_package", return_value=dest) as wp,
                patch(
                    "lab5_qms.cli.publish.publish_package",
                    return_value="published",
                ) as pp,
                patch("lab5_qms.cli.publish.seed_qm_rights") as seed,
                patch("lab5_qms.cli.publish.client", return_value=ctx),
            ):
                r = CliRunner().invoke(cli, [])
            self.assertEqual(r.exit_code, 0, r.output)
            wp.assert_called_once()
            pp.assert_called_once_with(dest.read_bytes(), timeout=600.0)
            seed.assert_called_once_with(session)
            self.assertIn("published", r.output)
            self.assertIn("seeded", r.output)


class TestSeedQmRightsV10(unittest.TestCase):
    def test_seed_function_has_no_acu_user_attach(self) -> None:
        src = (ROOT / "lab5_qms" / "publish.py").read_text(encoding="utf-8")
        start = src.index("def seed_qm_rights")
        body = src[start:]
        self.assertIn("QUALITY_MANAGER_ROLE", body)
        self.assertIn("_ensure_qm_roles_in_graph", body)
        self.assertNotIn("UsersInRoles", body)
        self.assertNotIn("_ensure_acu_user_quality_manager", body)
        helper = (ROOT / "e2e" / "helper.py").read_text(encoding="utf-8")
        self.assertIn("_ensure_acu_user_quality_manager", helper)
        self.assertIn("UsersInRoles", helper)
        self.assertIsNotNone(seed_qm_rights)

    def test_cli_seed_calls_seed_qm_rights(self) -> None:
        session = object()
        ctx = MagicMock()
        ctx.__enter__.return_value = session
        ctx.__exit__.return_value = None
        with (
            patch("lab5_qms.cli.publish.client", return_value=ctx),
            patch("lab5_qms.cli.publish.seed_qm_rights") as seed,
        ):
            r = CliRunner().invoke(cli, ["seed"])
        self.assertEqual(r.exit_code, 0, r.output)
        seed.assert_called_once_with(session)
        self.assertIn("seeded", r.output)


class TestPackModuleZipBytesV8(unittest.TestCase):
    def test_package_zip_name_constant(self) -> None:
        from lab5_qms import pack

        self.assertEqual(pack.PACKAGE_ZIP, "Lab5_QMS_Customization.zip")
        self.assertEqual(pack.ASSEMBLY_DLL, "Lab5.QMS.dll")
        with zipfile.ZipFile(io.BytesIO(pack.package_zip(ROOT))) as zf:
            self.assertIn("project.xml", zf.namelist())


if __name__ == "__main__":
    unittest.main()
