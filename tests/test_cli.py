#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T14 / T15 / T16 / I.cmd / V8 / V10: Click console script lab5-qms pack+publish+seed+deploy."""

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
from lab5_qms.publish import (  # noqa: E402
    PACKAGE_NAME,
    QM_SCREENS,
    QMS_ENDPOINT,
    QMS_VERSION,
    QUALITY_MANAGER_ROLE,
    package_description,
    publish_package,
    seed_qm_rights,
)

ELAPSED_RE = r"^\d+\.\d{2}s$"
PUBLISH_IMPORT_STEPS = (
    "drain in-flight publish",
    "digest skip or import",
    "drop File-item FrontendSources leftovers",
    "webpack NO_COLOR for SaveStatus",
    "publishBegin",
    "poll publishEnd",
    "wait QMS/22.200.001",
)
SEED_STEPS = (
    "seed Role",
    "seed RolesInGraph",
    "seed EntityMapping",
    "seed UsrQMSSetup",
    "seed Quality Queue GI",
    "seed Pages/QM aspx",
    "seed SiteMap SelectedUI=D",
)


def _tiny_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("project.xml", b'<Customization description="x"/>')
    return buf.getvalue()


def _session_ctx(session: object) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__.return_value = session
    ctx.__exit__.return_value = None
    return ctx


def parse_progress(text: str) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 4:
            rows.append((parts[0], parts[1], parts[2], parts[3]))
    return rows


class TestProjectScriptsICmd(unittest.TestCase):
    def test_pyproject_wires_lab5_qms_console_script(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[project.scripts]", text)
        self.assertIn('lab5-qms = "lab5_qms.cli:main"', text)
        self.assertIn("[build-system]", text)
        self.assertIn("click>=8.1", text)
        self.assertIn("[dependency-groups]", text)
        self.assertIn("ruff", text)
        self.assertIn("[tool.ruff]", text)

    def test_makefile_pack_uses_lab5_qms(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("lab5-qms pack", makefile)
        self.assertIn("lab5-qms deploy", makefile)
        self.assertNotIn("./pack.py", makefile)


class TestCliHelpICmd(unittest.TestCase):
    def test_help_lists_pack_publish_seed_deploy(self) -> None:
        r = CliRunner().invoke(cli, ["--help"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertIn("pack", r.output)
        self.assertIn("publish", r.output)
        self.assertIn("seed", r.output)
        self.assertIn("deploy", r.output)
        self.assertIn("Lab5_QMS_Customization.zip", r.output)
        self.assertIn("CustomizationApi", r.output)
        self.assertIn("Quality Manager", r.output)

    def test_naked_emits_help_not_deploy(self) -> None:
        with (
            patch("lab5_qms.cli.pack.write_package") as wp,
            patch("lab5_qms.cli.publish.publish_package") as pp,
            patch("lab5_qms.cli.publish.seed_qm_rights") as seed,
            patch("lab5_qms.cli.publish.client") as client,
        ):
            r = CliRunner().invoke(cli, [])
        self.assertEqual(r.exit_code, 0, r.output)
        wp.assert_not_called()
        pp.assert_not_called()
        seed.assert_not_called()
        client.assert_not_called()
        self.assertIn("Usage:", r.output)
        self.assertIn("pack", r.output)
        self.assertIn("publish", r.output)
        self.assertIn("seed", r.output)
        self.assertIn("deploy", r.output)


class TestCliPackV8(unittest.TestCase):
    def test_pack_ensures_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            with patch("lab5_qms.pack.ensure_assembly") as ensure:
                r = CliRunner().invoke(cli, ["pack", "-o", str(dest)])
            self.assertEqual(r.exit_code, 0, r.output)
            ensure.assert_called_once()

    def test_pack_writes_zip_without_role_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            with patch("lab5_qms.pack.ensure_assembly"):
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
    def test_deploy_packs_publishes_and_seeds(self) -> None:
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
                r = CliRunner().invoke(cli, ["deploy"])
            self.assertEqual(r.exit_code, 0, r.output)
            wp.assert_called_once()
            pp.assert_called_once_with(dest.read_bytes(), timeout=900.0)
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


class TestCliProgressICmdV10(unittest.TestCase):
    def test_progress_line_shape(self) -> None:
        from lab5_qms.progress import emit

        buf = io.StringIO()
        emit("pack zip", "Lab5_QMS_Customization.zip", "ok", 0.12, file=buf)
        step, target, result, elapsed = parse_progress(buf.getvalue())[0]
        self.assertEqual(step, "pack zip")
        self.assertEqual(target, "Lab5_QMS_Customization.zip")
        self.assertEqual(result, "ok")
        self.assertEqual(elapsed, "0.12s")

    def test_pack_progress_on_stderr_stdout_is_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            with patch("lab5_qms.pack.ensure_assembly"):
                r = CliRunner().invoke(cli, ["pack", "-o", str(dest)])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(r.stdout.strip(), str(dest))
        self.assertNotIn("\t", r.stdout)
        rows = parse_progress(r.stderr)
        self.assertEqual([row[0] for row in rows], ["pack zip"])
        self.assertEqual(rows[0][1], str(dest))
        self.assertEqual(rows[0][2], "ok")
        self.assertRegex(rows[0][3], ELAPSED_RE)

    def test_publish_skip_progress(self) -> None:
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = MagicMock()
        session.customization_published.return_value = [PACKAGE_NAME]
        session.list_endpoints.return_value = [("QMS", QMS_VERSION)]
        err = io.StringIO()
        with (
            patch("lab5_qms.publish.client", return_value=_session_ctx(session)),
            patch("lab5_qms.publish.drain_publish"),
            patch("lab5_qms.publish.published_description", return_value=desc),
            patch("lab5_qms.progress.sys.stderr", err),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "already published")
        rows = parse_progress(err.getvalue())
        self.assertEqual(
            [row[0] for row in rows],
            ["drain in-flight publish", "digest skip or import"],
        )
        self.assertEqual(rows[1][2], "skip")
        self.assertNotIn("publishBegin", err.getvalue())
        for row in rows:
            self.assertRegex(row[3], ELAPSED_RE)

    def test_publish_import_progress(self) -> None:
        zip_bytes = _tiny_zip()
        session = MagicMock()
        session.customization_published.return_value = []
        session.customization_publish_end.return_value = {"isCompleted": True}
        err = io.StringIO()
        with (
            patch("lab5_qms.publish.client", return_value=_session_ctx(session)),
            patch("lab5_qms.publish.drain_publish"),
            patch("lab5_qms.publish.publish_begin"),
            patch("lab5_qms.publish.wait_published"),
            patch("lab5_qms.publish._remove_file_item_frontend_leftovers"),
            patch("lab5_qms.publish._ensure_webpack_no_color"),
            patch("lab5_qms.progress.sys.stderr", err),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        rows = parse_progress(err.getvalue())
        self.assertEqual([row[0] for row in rows], list(PUBLISH_IMPORT_STEPS))
        self.assertEqual(rows[1][2], "import")
        self.assertEqual(rows[4][1], PACKAGE_NAME)
        self.assertEqual(rows[6][0], "wait QMS/22.200.001")
        self.assertEqual(rows[6][1], QMS_ENDPOINT)
        session.customization_import.assert_called_once()
        for row in rows:
            self.assertEqual(row[2], "import" if row[0].startswith("digest") else "ok")
            self.assertRegex(row[3], ELAPSED_RE)

    def test_seed_progress(self) -> None:
        session = MagicMock()
        err = io.StringIO()
        with (
            patch(
                "lab5_qms.publish.bootstrap_endpoint",
                return_value="Bootstrap/1.4.0",
            ),
            patch("lab5_qms.publish._ensure_quality_manager_role_row"),
            patch("lab5_qms.publish._ensure_qm_roles_in_graph"),
            patch("lab5_qms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("lab5_qms.publish._ensure_qms_setup_rows"),
            patch("lab5_qms.publish._ensure_quality_queue_gi"),
            patch("lab5_qms.publish._ensure_qm_aspx_pages"),
            patch("lab5_qms.publish._ensure_qm_selected_ui"),
            patch("lab5_qms.progress.sys.stderr", err),
        ):
            seed_qm_rights(session)
        rows = parse_progress(err.getvalue())
        self.assertEqual([row[0] for row in rows], list(SEED_STEPS))
        self.assertEqual(rows[0][1], QUALITY_MANAGER_ROLE)
        self.assertEqual(rows[1][1], ",".join(QM_SCREENS))
        self.assertEqual(rows[2][1], "Tests,Results")
        self.assertEqual(rows[3][1], "QORD,QNCR")
        self.assertEqual(rows[4][1], "QM401000")
        self.assertEqual(rows[5][1], "REST")
        self.assertEqual(rows[6][1], ",".join(QM_SCREENS))
        session.put.assert_called_once()
        for row in rows:
            self.assertEqual(row[2], "ok")
            self.assertRegex(row[3], ELAPSED_RE)

    def test_deploy_progress_all_steps_stdout_status(self) -> None:
        zip_bytes = _tiny_zip()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            dest.write_bytes(zip_bytes)
            session = MagicMock()
            session.customization_published.return_value = []
            session.customization_publish_end.return_value = {"isCompleted": True}
            with (
                patch("lab5_qms.cli.pack.write_package", return_value=dest),
                patch(
                    "lab5_qms.publish.client",
                    return_value=_session_ctx(session),
                ),
                patch("lab5_qms.publish.drain_publish"),
                patch("lab5_qms.publish.publish_begin"),
                patch("lab5_qms.publish.wait_published"),
                patch("lab5_qms.publish._remove_file_item_frontend_leftovers"),
                patch("lab5_qms.publish._ensure_webpack_no_color"),
                patch(
                    "lab5_qms.publish.bootstrap_endpoint",
                    return_value="Bootstrap/1.4.0",
                ),
                patch("lab5_qms.publish._ensure_quality_manager_role_row"),
                patch("lab5_qms.publish._ensure_qm_roles_in_graph"),
                patch("lab5_qms.publish._ensure_qms_detail_mappings", return_value=0),
                patch("lab5_qms.publish._ensure_qms_setup_rows"),
                patch("lab5_qms.publish._ensure_quality_queue_gi"),
                patch("lab5_qms.publish._ensure_qm_aspx_pages"),
                patch("lab5_qms.publish._ensure_qm_selected_ui"),
            ):
                r = CliRunner().invoke(cli, ["deploy", "-o", str(dest)])
        self.assertEqual(r.exit_code, 0, r.output)
        stdout_lines = [line for line in r.stdout.splitlines() if line]
        self.assertEqual(stdout_lines, [str(dest), "published", "seeded"])
        self.assertNotIn("\t", r.stdout)
        steps = [row[0] for row in parse_progress(r.stderr)]
        self.assertEqual(
            steps,
            ["pack zip", *PUBLISH_IMPORT_STEPS, *SEED_STEPS],
        )


class TestPackModuleZipBytesV8(unittest.TestCase):
    def test_package_zip_name_constant(self) -> None:
        from lab5_qms import pack

        self.assertEqual(pack.PACKAGE_ZIP, "Lab5_QMS_Customization.zip")
        self.assertEqual(pack.ASSEMBLY_DLL, "Lab5.QMS.dll")
        with zipfile.ZipFile(io.BytesIO(pack.package_zip(ROOT))) as zf:
            self.assertIn("project.xml", zf.namelist())


if __name__ == "__main__":
    unittest.main()
