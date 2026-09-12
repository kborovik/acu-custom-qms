#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T14 / T15 / T16 / T40 / T41 / T42 / T43 / T47 / T50 / T51 / T54 / T57 / T58 / I.cmd / V8 / V10 / V18 / V19 / V20 / V26 / B8 / B9 / B10 / B12 / B13 / B15 / B16: Click console script acuqms build+publish+seed+deploy+unpublish."""

from __future__ import annotations

import inspect
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acuqms.cli import cli  # noqa: E402
from acuqms.publish import (  # noqa: E402
    ACUBOOTSTRAP,
    INSPECTION_PLAN_PATH,
    OOTB_WEBPACK_REFERENCE,
    OPTIMIZED_EXPORT_NRE_EXTRA_RECYCLES,
    OPTIMIZED_EXPORT_NRE_KIND,
    PACKAGE_NAME,
    QM_SCREENS,
    QMS_ENDPOINT,
    QMS_VERSION,
    QUALITY_MANAGER_ROLE,
    SHARED_WEBPACK_SCREENS,
    _inspection_plan_kind,
    _recycle_app_pool,
    package_description,
    publish_package,
    qms_endpoint_live,
    remaining_published,
    restore_ootb_webpack_ps1,
    seed_qm_rights,
    unpublish_db_leftover_sql,
    unpublish_package,
    wait_published,
    wait_rest,
)

ELAPSED_RE = r"^\d+\.\d{2}s$"
PUBLISH_IMPORT_STEPS = (
    "webpack NO_COLOR for SaveStatus",
    "drain in-flight publish",
    "drop File-item FrontendSources leftovers",
    "digest skip or import",
    "publishBegin",
    "poll publishEnd",
    "seed EntityMapping",
    "seed Pages/QM aspx",
    "recycle app pool",
    "wait QMS/22.200.001",
)
PUBLISH_SKIP_STEPS = PUBLISH_IMPORT_STEPS[:4]
SEED_STEPS = (
    "seed Role",
    "seed RolesInGraph",
    "seed EntityMapping",
    "seed Pages/QM aspx",
    "seed UsrQMSSetup",
    "seed Quality Queue GI",
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


def _plan_get(
    status: int,
    body: object | None = None,
    *,
    html: bool = False,
    text: str | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    if html:
        response.json.side_effect = ValueError("Expecting value")
        response.text = text if text is not None else "<html>login</html>"
        return response
    if body is None:
        body = [] if status == 200 else {"message": "error"}
    response.json.return_value = body
    response.text = text if text is not None else str(body)
    return response


def _nre_get() -> MagicMock:
    return _plan_get(
        500,
        {
            "exceptionType": "System.NullReferenceException",
            "exceptionMessage": "OptimizedExportProviderBuilder",
        },
    )


def _session_with_plan(*, published: bool = True, plan_status: int = 200) -> MagicMock:
    session = MagicMock()
    session.customization_published.return_value = [PACKAGE_NAME] if published else []
    session.list_endpoints.return_value = [("QMS", QMS_VERSION)]
    session.customization_publish_end.return_value = {"isCompleted": True}
    session._http.get.return_value = _plan_get(plan_status)
    return session


def parse_progress(text: str) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 4:
            rows.append((parts[0], parts[1], parts[2], parts[3]))
    return rows


class TestProjectScriptsICmd(unittest.TestCase):
    def test_pyproject_wires_acuqms_console_script(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[project.scripts]", text)
        self.assertIn('name = "acuqms"', text)
        self.assertIn('acuqms = "acuqms.cli:main"', text)
        self.assertIn('include = ["acuqms*"]', text)
        self.assertNotIn("lab5-qms", text)
        self.assertNotIn("lab5_qms", text)
        self.assertIn("[build-system]", text)
        self.assertIn("click>=8.1", text)
        self.assertIn("[dependency-groups]", text)
        self.assertIn("ruff", text)
        self.assertIn("[tool.ruff]", text)

    def test_makefile_build_uses_acuqms(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("acuqms build", makefile)
        self.assertIn("acuqms deploy", makefile)
        self.assertIn("acuqms unpublish", makefile)
        self.assertNotIn("lab5-qms", makefile)
        self.assertNotIn("./pack.py", makefile)


class TestCliHelpICmd(unittest.TestCase):
    def test_help_lists_build_publish_seed_deploy(self) -> None:
        r = CliRunner().invoke(cli, ["--help"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertIn("build", cli.commands)
        self.assertNotIn("pack", cli.commands)
        self.assertIn("build", r.output)
        self.assertIn("publish", r.output)
        self.assertIn("seed", r.output)
        self.assertIn("deploy", r.output)
        self.assertIn("unpublish", r.output)
        self.assertIn("Lab5_QMS_Customization.zip", r.output)
        self.assertIn("CustomizationApi", r.output)
        self.assertIn("Quality Manager", r.output)

    def test_naked_emits_help_not_deploy(self) -> None:
        with (
            patch("acuqms.cli.pack.write_package") as wp,
            patch("acuqms.cli.publish.publish_package") as pp,
            patch("acuqms.cli.publish.seed_qm_rights") as seed,
            patch("acuqms.cli.publish.client") as client,
        ):
            r = CliRunner().invoke(cli, [])
        self.assertEqual(r.exit_code, 0, r.output)
        wp.assert_not_called()
        pp.assert_not_called()
        seed.assert_not_called()
        client.assert_not_called()
        self.assertIn("Usage:", r.output)
        self.assertIn("build", r.output)
        self.assertIn("publish", r.output)
        self.assertIn("seed", r.output)
        self.assertIn("deploy", r.output)
        self.assertIn("unpublish", r.output)


class TestCliPackV8(unittest.TestCase):
    def test_pack_ensures_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            with patch("acuqms.pack.ensure_assembly") as ensure:
                r = CliRunner().invoke(cli, ["build", "-o", str(dest)])
            self.assertEqual(r.exit_code, 0, r.output)
            ensure.assert_called_once()

    def test_pack_writes_zip_without_role_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            with patch("acuqms.pack.ensure_assembly"):
                r = CliRunner().invoke(cli, ["build", "-o", str(dest)])
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
                patch("acuqms.cli.pack.write_package", return_value=dest) as wp,
                patch(
                    "acuqms.cli.publish.publish_package",
                    return_value="published",
                ) as pp,
                patch("acuqms.cli.publish.seed_qm_rights") as seed,
                patch("acuqms.cli.publish.client", return_value=ctx),
                patch("acuqms.cli.publish.qms_endpoint_live", return_value=True),
            ):
                r = CliRunner().invoke(cli, ["deploy"])
            self.assertEqual(r.exit_code, 0, r.output)
            wp.assert_called_once()
            pp.assert_called_once_with(dest.read_bytes(), timeout=900.0)
            seed.assert_called_once_with(session)
            self.assertIn("published", r.output)
            self.assertIn("seeded", r.output)

    def test_deploy_skip_then_seed_then_not_live_imports(self) -> None:
        """V18 / B8: skip then seed then not-live → import+wait."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Lab5_QMS_Customization.zip"
            dest.write_bytes(b"PK\x03\x04fake")
            session = object()
            ctx = MagicMock()
            ctx.__enter__.return_value = session
            ctx.__exit__.return_value = None
            with (
                patch("acuqms.cli.pack.write_package", return_value=dest),
                patch(
                    "acuqms.cli.publish.publish_package",
                    side_effect=["already published", "published"],
                ) as pp,
                patch("acuqms.cli.publish.seed_qm_rights") as seed,
                patch("acuqms.cli.publish.client", return_value=ctx),
                patch("acuqms.cli.publish.qms_endpoint_live", return_value=False),
            ):
                r = CliRunner().invoke(cli, ["deploy"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(pp.call_count, 2)
        self.assertEqual(seed.call_count, 2)
        stdout_lines = [line for line in r.stdout.splitlines() if line]
        self.assertEqual(
            stdout_lines,
            [str(dest), "already published", "published", "seeded"],
        )


class TestSeedQmRightsV10(unittest.TestCase):
    def test_seed_function_has_no_acu_user_attach(self) -> None:
        src = (ROOT / "acuqms" / "publish.py").read_text(encoding="utf-8")
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
            patch("acuqms.cli.publish.client", return_value=ctx),
            patch("acuqms.cli.publish.seed_qm_rights") as seed,
        ):
            r = CliRunner().invoke(cli, ["seed"])
        self.assertEqual(r.exit_code, 0, r.output)
        seed.assert_called_once_with(session)
        self.assertIn("seeded", r.output)


class TestCliProgressICmdV10(unittest.TestCase):
    def test_progress_line_shape(self) -> None:
        from acuqms.progress import emit

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
            with patch("acuqms.pack.ensure_assembly"):
                r = CliRunner().invoke(cli, ["build", "-o", str(dest)])
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
        session = _session_with_plan(plan_status=200)
        err = io.StringIO()
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.progress.sys.stderr", err),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "already published")
        session._http.get.assert_called_with(INSPECTION_PLAN_PATH)
        rows = parse_progress(err.getvalue())
        self.assertEqual([row[0] for row in rows], list(PUBLISH_SKIP_STEPS))
        self.assertEqual(rows[3][2], "skip")
        self.assertNotIn("publishBegin", err.getvalue())
        for row in rows:
            self.assertRegex(row[3], ELAPSED_RE)

    def test_publish_skip_forced_when_webpack_missing(self) -> None:
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=200)
        order: list[str] = []

        def webpack() -> bool:
            order.append("webpack")
            return False

        def make_client() -> MagicMock:
            order.append("client")
            return _session_ctx(session)

        with (
            patch("acuqms.publish.client", side_effect=make_client),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published"),
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", side_effect=webpack),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=True,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        self.assertEqual(order[0], "webpack")
        self.assertLess(order.index("webpack"), order.index("client"))
        session.customization_import.assert_called_once()
        session.customization_publish_end.assert_called()

    def test_publish_skip_forced_when_pool_recycled(self) -> None:
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=200)
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published"),
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=True),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        session.customization_import.assert_called_once()

    def test_publish_import_progress(self) -> None:
        zip_bytes = _tiny_zip()
        session = _session_with_plan(published=False, plan_status=404)
        err = io.StringIO()
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published"),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", err),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        rows = parse_progress(err.getvalue())
        self.assertEqual([row[0] for row in rows], list(PUBLISH_IMPORT_STEPS))
        self.assertEqual(rows[3][2], "import")
        self.assertEqual(rows[4][1], PACKAGE_NAME)
        wait_idx = PUBLISH_IMPORT_STEPS.index("wait QMS/22.200.001")
        maps_idx = PUBLISH_IMPORT_STEPS.index("seed EntityMapping")
        aspx_idx = PUBLISH_IMPORT_STEPS.index("seed Pages/QM aspx")
        recycle_idx = PUBLISH_IMPORT_STEPS.index("recycle app pool")
        self.assertLess(maps_idx, aspx_idx)
        self.assertLess(aspx_idx, recycle_idx)
        self.assertLess(recycle_idx, wait_idx)
        self.assertEqual(rows[maps_idx][1], "Tests,Results")
        self.assertEqual(rows[aspx_idx][1], "REST")
        self.assertEqual(rows[recycle_idx][1], "IIS")
        self.assertEqual(rows[wait_idx][0], "wait QMS/22.200.001")
        self.assertEqual(rows[wait_idx][1], QMS_ENDPOINT)
        session.customization_import.assert_called_once()
        for row in rows:
            self.assertEqual(row[2], "import" if row[0].startswith("digest") else "ok")
            self.assertRegex(row[3], ELAPSED_RE)

    def test_publish_skip_when_inspection_plan_200(self) -> None:
        """V18 / I.cmd: InspectionPlan 200 JSON array + digest match → already published."""
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=200)
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "already published")
        session.customization_import.assert_not_called()
        session._http.get.assert_called_with(INSPECTION_PLAN_PATH)

    def test_publish_import_when_inspection_plan_404_despite_leftover_listing(
        self,
    ) -> None:
        """V18: leftover getPublished + GET /entity QMS listing ! skip on 404."""
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=404)
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published") as wait,
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        session.customization_import.assert_called_once()
        wait.assert_called_once_with()
        session._http.get.assert_called_with(INSPECTION_PLAN_PATH)

    def test_publish_import_when_inspection_plan_200_html_despite_digest_match(
        self,
    ) -> None:
        """V18 / B8: 200 HTML + digest match is not live → import, not skip."""
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=200)
        session._http.get.return_value = _plan_get(200, html=True)
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published") as wait,
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        session.customization_import.assert_called_once()
        wait.assert_called_once_with()
        session._http.get.assert_called_with(INSPECTION_PLAN_PATH)

    def test_publish_skip_requires_json_array_not_mere_200(self) -> None:
        """V18 / B8: skip already published requires JSON array, not mere 200."""
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=200)
        session._http.get.return_value = _plan_get(
            200, {"message": "Endpoint [QMS/22.200.001] not found"}
        )
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published") as wait,
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        session.customization_import.assert_called_once()
        wait.assert_called_once_with()

    def test_qms_endpoint_live_200_empty_ok(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _plan_get(200, [])
        self.assertTrue(qms_endpoint_live(session))
        session._http.get.assert_called_once_with(INSPECTION_PLAN_PATH)

    def test_qms_endpoint_live_200_html_not_live(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _plan_get(200, html=True)
        self.assertFalse(qms_endpoint_live(session))
        session._http.get.assert_called_once_with(INSPECTION_PLAN_PATH)

    def test_qms_endpoint_live_200_error_dict_not_live(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _plan_get(200, {"message": "error"})
        self.assertFalse(qms_endpoint_live(session))
        session._http.get.assert_called_once_with(INSPECTION_PLAN_PATH)

    def test_qms_endpoint_live_401_not_live(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _plan_get(401)
        self.assertFalse(qms_endpoint_live(session))
        session._http.get.assert_called_once_with(INSPECTION_PLAN_PATH)

    def test_qms_endpoint_live_404(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _plan_get(404)
        self.assertFalse(qms_endpoint_live(session))
        session._http.get.assert_called_once_with(INSPECTION_PLAN_PATH)

    def test_ensure_published_skip_then_seed_then_not_live_imports(self) -> None:
        """V18 / B8: skip then seed then not-live → import+wait."""
        from e2e import helper

        helper._published = None
        helper._publish_error = None
        zip_bytes = _tiny_zip()
        try:
            with (
                patch("e2e.helper.pack.package_zip", return_value=zip_bytes),
                patch(
                    "e2e.helper.publish_package",
                    side_effect=["already published", "published"],
                ) as pp,
                patch("e2e.helper.ensure_qm_rights") as seed,
                patch("e2e.helper.client", return_value=_session_ctx(MagicMock())),
                patch("e2e.helper.qms_endpoint_live", return_value=False),
            ):
                status = helper.ensure_published(timeout=90.0)
        finally:
            helper._published = None
            helper._publish_error = None
        self.assertEqual(status, "published")
        self.assertEqual(pp.call_count, 2)
        self.assertEqual(seed.call_count, 2)

    def test_wait_published_ignores_leftover_entity_listing(self) -> None:
        """V18: GET /entity listing QMS is leftover; wait needs InspectionPlan 200."""
        session = _session_with_plan(plan_status=404)
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.time.sleep"),
            patch(
                "acuqms.publish.time.monotonic",
                side_effect=[0.0, 0.0, 10.0],
            ),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                wait_published(timeout=5.0, poll=1.0)
        msg = str(ctx.exception)
        self.assertIn("InspectionPlan", msg)
        self.assertIn("last GET 404", msg)
        session._http.get.assert_called_with(INSPECTION_PLAN_PATH)

    def test_wait_published_returns_when_inspection_plan_200(self) -> None:
        session = _session_with_plan(plan_status=200)
        session.list_endpoints.return_value = []
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            wait_published(timeout=5.0, poll=1.0)
        session._http.get.assert_called_with(INSPECTION_PLAN_PATH)

    def test_seed_progress(self) -> None:
        session = MagicMock()
        err = io.StringIO()
        with (
            patch(
                "acuqms.publish.bootstrap_endpoint",
                return_value="Bootstrap/1.4.0",
            ),
            patch("acuqms.publish._ensure_quality_manager_role_row"),
            patch("acuqms.publish._ensure_qm_roles_in_graph"),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qms_setup_rows"),
            patch("acuqms.publish._ensure_quality_queue_gi"),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._ensure_qm_selected_ui"),
            patch("acuqms.progress.sys.stderr", err),
        ):
            seed_qm_rights(session)
        rows = parse_progress(err.getvalue())
        self.assertEqual([row[0] for row in rows], list(SEED_STEPS))
        self.assertEqual(rows[0][1], QUALITY_MANAGER_ROLE)
        self.assertEqual(rows[1][1], ",".join(QM_SCREENS))
        self.assertEqual(rows[2][1], "Tests,Results")
        self.assertEqual(rows[3][1], "REST")
        self.assertEqual(rows[4][1], "QORD,QNCR")
        self.assertEqual(rows[5][1], "QM401000")
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
            session = _session_with_plan(published=False, plan_status=404)
            with (
                patch("acuqms.cli.pack.write_package", return_value=dest),
                patch(
                    "acuqms.publish.client",
                    return_value=_session_ctx(session),
                ),
                patch("acuqms.publish.drain_publish"),
                patch("acuqms.publish.publish_begin"),
                patch("acuqms.publish.wait_published"),
                patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
                patch(
                    "acuqms.publish._remove_file_item_frontend_leftovers",
                    return_value=False,
                ),
                patch(
                    "acuqms.publish._webpack_tenant_screens_missing",
                    return_value=False,
                ),
                patch(
                    "acuqms.publish.bootstrap_endpoint",
                    return_value="Bootstrap/1.4.0",
                ),
                patch("acuqms.publish._ensure_quality_manager_role_row"),
                patch("acuqms.publish._ensure_qm_roles_in_graph"),
                patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
                patch("acuqms.publish._ensure_qms_setup_rows"),
                patch("acuqms.publish._ensure_quality_queue_gi"),
                patch("acuqms.publish._ensure_qm_aspx_pages"),
                patch("acuqms.publish._recycle_app_pool"),
                patch("acuqms.publish._ensure_qm_selected_ui"),
                patch("acuqms.publish.qms_endpoint_live", return_value=True),
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


class TestV19_WaitPublished600s(unittest.TestCase):
    def test_wait_published_default_is_600_not_120(self) -> None:
        params = inspect.signature(wait_published).parameters
        self.assertEqual(params["timeout"].default, 600.0)
        src = (ROOT / "acuqms" / "publish.py").read_text(encoding="utf-8")
        self.assertNotIn("wait_published(timeout=120", src)
        self.assertIn("wait_published()", src)

    def test_publish_package_wait_ignores_cli_timeout(self) -> None:
        zip_bytes = _tiny_zip()
        session = _session_with_plan(published=False, plan_status=404)
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published") as wait,
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes, timeout=90.0)
        self.assertEqual(status, "published")
        wait.assert_called_once_with()

    def test_recycle_app_pool_wait_rest_not_wait_published(self) -> None:
        """V19 / B12: recycle waits for GET /entity 120s, not wait_published 600s."""
        inst = MagicMock()
        inst.ssh = "Administrator@host"
        session = _session_with_plan(plan_status=200)
        with (
            patch("acuqms.publish.instance", return_value=inst),
            patch("acuqms.publish.ssh_run"),
            patch("acuqms.publish.wait_rest") as rest,
            patch("acuqms.publish.wait_published") as wait,
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
        ):
            _recycle_app_pool()
        rest.assert_called_once_with()
        wait.assert_not_called()
        src = (ROOT / "acuqms" / "publish.py").read_text(encoding="utf-8")
        body = src[
            src.index("def _recycle_app_pool") : src.index("\ndef qms_setup_insert_sql")
        ]
        self.assertIn("wait_rest()", body)
        self.assertNotIn("wait_published()", body)

    def _timeout_after_one_poll(self, session: MagicMock) -> str:
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.time.sleep"),
            patch(
                "acuqms.publish.time.monotonic",
                side_effect=[0.0, 0.0, 10.0],
            ),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                wait_published(timeout=5.0, poll=1.0)
        return str(ctx.exception)

    def test_wait_timeout_reports_last_get_html(self) -> None:
        session = _session_with_plan(plan_status=200)
        session._http.get.return_value = _plan_get(200, html=True)
        msg = self._timeout_after_one_poll(session)
        self.assertIn("last GET 200 HTML", msg)
        self.assertIn("5s", msg)

    def test_wait_timeout_reports_last_get_error_object(self) -> None:
        session = _session_with_plan(plan_status=200)
        session._http.get.return_value = _plan_get(
            200, {"message": "Endpoint [QMS/22.200.001] not found"}
        )
        msg = self._timeout_after_one_poll(session)
        self.assertIn("last GET 200 error object", msg)

    def test_wait_timeout_reports_last_get_transport(self) -> None:
        session = _session_with_plan(plan_status=200)
        session._http.get.side_effect = httpx.TransportError("boom")
        msg = self._timeout_after_one_poll(session)
        self.assertIn("last GET transport", msg)

    def test_wait_published_emits_start_and_poll_heartbeat(self) -> None:
        """V19 / B12: start + last-GET heartbeat; heartbeat is not 4-col progress."""
        session = _session_with_plan(plan_status=200)
        session._http.get.side_effect = [
            _plan_get(404),
            _plan_get(200, []),
        ]
        err = io.StringIO()
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.time.sleep"),
            patch("acuqms.progress.sys.stderr", err),
        ):
            wait_published(timeout=20.0, poll=1.0)
        lines = [line for line in err.getvalue().splitlines() if line]
        self.assertEqual(lines[0], f"wait {QMS_ENDPOINT}\tstart")
        self.assertIn(f"wait {QMS_ENDPOINT}\tlast GET 404", lines)
        self.assertIn(f"wait {QMS_ENDPOINT}\tlast GET 200 JSON array", lines)
        for line in lines:
            self.assertNotEqual(len(line.split("\t")), 4)
        self.assertEqual(parse_progress(err.getvalue()), [])

    def test_wait_published_reuses_session_across_polls(self) -> None:
        """V19 / B12: one client() session covers successive InspectionPlan GETs."""
        session = _session_with_plan(plan_status=200)
        session._http.get.side_effect = [
            _plan_get(404),
            _plan_get(200, []),
        ]
        with (
            patch(
                "acuqms.publish.client", return_value=_session_ctx(session)
            ) as make_client,
            patch("acuqms.publish.time.sleep"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            wait_published(timeout=20.0, poll=1.0)
        self.assertEqual(make_client.call_count, 1)
        self.assertEqual(session._http.get.call_count, 2)

    def test_ssh_run_defaults_to_ssh_timeout(self) -> None:
        """V19 / B12: ssh_run times out; default is not None."""
        from acuqms.acu import SSH_TIMEOUT, ssh_run

        params = inspect.signature(ssh_run).parameters
        self.assertEqual(params["timeout"].default, SSH_TIMEOUT)
        src = (ROOT / "acuqms" / "acu.py").read_text(encoding="utf-8")
        self.assertIn("timeout: float = SSH_TIMEOUT", src)
        self.assertNotIn("timeout: float | None = None", src)


class TestV20_EntityMappingBeforeWait(unittest.TestCase):
    def _import_order(
        self,
        *,
        maps_return: int = 0,
        maps_error: Exception | None = None,
    ) -> tuple[str | BaseException, list[str]]:
        zip_bytes = _tiny_zip()
        session = _session_with_plan(published=False, plan_status=404)
        order: list[str] = []

        def maps() -> int:
            order.append("maps")
            if maps_error is not None:
                raise maps_error
            return maps_return

        def aspx() -> None:
            order.append("aspx")

        def recycle() -> None:
            order.append("recycle")

        def wait() -> None:
            order.append("wait")

        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.wait_published", side_effect=wait),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", side_effect=maps),
            patch("acuqms.publish._ensure_qm_aspx_pages", side_effect=aspx),
            patch("acuqms.publish._recycle_app_pool", side_effect=recycle),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            try:
                status: str | BaseException = publish_package(zip_bytes)
            except Exception as exc:
                status = exc
        return status, order

    def test_maps_then_wait_when_maps_present(self) -> None:
        """V20 / B13: recycle even when nested maps already exist."""
        status, order = self._import_order(maps_return=0)
        self.assertEqual(status, "published")
        self.assertEqual(order, ["maps", "aspx", "recycle", "wait"])

    def test_maps_recycle_then_wait_when_inserted(self) -> None:
        status, order = self._import_order(maps_return=1)
        self.assertEqual(status, "published")
        self.assertEqual(order, ["maps", "aspx", "recycle", "wait"])

    def test_wait_not_called_when_maps_fail(self) -> None:
        status, order = self._import_order(
            maps_error=RuntimeError(
                "EntityMapping seed: 0/17 Tests/Results maps present"
            )
        )
        self.assertIsInstance(status, RuntimeError)
        self.assertIn("EntityMapping seed", str(status))
        self.assertEqual(order, ["maps"])

    def test_skip_does_not_seed_maps_in_publish_package(self) -> None:
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=200)
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings") as maps,
            patch("acuqms.publish.wait_published") as wait,
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "already published")
        maps.assert_not_called()
        wait.assert_not_called()

    def test_publish_package_source_maps_before_wait(self) -> None:
        src = (ROOT / "acuqms" / "publish.py").read_text(encoding="utf-8")
        body = src[
            src.index("def publish_package") : src.index("\ndef roles_in_graph_rows")
        ]
        self.assertLess(
            body.index("_ensure_qms_detail_mappings"),
            body.index("_ensure_qm_aspx_pages"),
        )
        self.assertLess(
            body.index("_ensure_qm_aspx_pages"),
            body.index("wait_published()"),
        )
        self.assertLess(body.index("_recycle_app_pool"), body.index("wait_published()"))
        self.assertLess(
            body.index("_ensure_qm_aspx_pages"),
            body.index("_recycle_app_pool"),
        )
        self.assertNotIn("if maps_inserted:", body)

    def test_wait_get_200_json_array_after_maps(self) -> None:
        """V20 / B10: wait_published InspectionPlan GET 200 JSON array runs after maps."""
        zip_bytes = _tiny_zip()
        publish_session = _session_with_plan(published=False, plan_status=404)
        wait_session = _session_with_plan(plan_status=200)
        order: list[str] = []
        clients = [_session_ctx(publish_session), _session_ctx(wait_session)]

        def make_client() -> MagicMock:
            return clients.pop(0)

        def maps() -> int:
            order.append("maps")
            return 0

        def tracking_get(*_args: object, **_kwargs: object) -> MagicMock:
            order.append("get")
            return _plan_get(200, [])

        wait_session._http.get.side_effect = tracking_get
        with (
            patch("acuqms.publish.client", side_effect=make_client),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", side_effect=maps),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        self.assertEqual(order, ["maps", "get"])
        self.assertEqual(clients, [])


class TestV20_SecondRecycleOnOptimizedExportNre(unittest.TestCase):
    def _recycle(
        self,
        session: MagicMock,
        *,
        inst_ssh: str | None = "Administrator@host",
    ) -> tuple[MagicMock, MagicMock]:
        inst = MagicMock()
        inst.ssh = inst_ssh
        with (
            patch("acuqms.publish.instance", return_value=inst),
            patch("acuqms.publish.ssh_run") as ssh,
            patch("acuqms.publish.wait_rest") as rest,
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
        ):
            _recycle_app_pool()
        return ssh, rest

    def test_second_recycle_on_nre(self) -> None:
        """V20 / B15: InspectionPlan 500 OptimizedExport NRE → one extra recycle."""
        session = MagicMock()
        session._http.get.return_value = _nre_get()
        ssh, rest = self._recycle(session)
        self.assertEqual(ssh.call_count, 2)
        self.assertEqual(rest.call_count, 2)
        self.assertEqual(session._http.get.call_count, 1)
        session._http.get.assert_called_with(INSPECTION_PLAN_PATH)

    def test_no_second_recycle_when_inspection_plan_200(self) -> None:
        session = _session_with_plan(plan_status=200)
        ssh, rest = self._recycle(session)
        self.assertEqual(ssh.call_count, 1)
        self.assertEqual(rest.call_count, 1)

    def test_no_second_recycle_when_inspection_plan_404(self) -> None:
        session = _session_with_plan(plan_status=404)
        ssh, rest = self._recycle(session)
        self.assertEqual(ssh.call_count, 1)
        self.assertEqual(rest.call_count, 1)

    def test_no_second_recycle_when_500_is_not_optimized_export_nre(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _plan_get(
            500, {"message": "The view  doesn't exist"}
        )
        ssh, rest = self._recycle(session)
        self.assertEqual(ssh.call_count, 1)
        self.assertEqual(rest.call_count, 1)

    def test_bound_one_extra_recycle(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _nre_get()
        ssh, rest = self._recycle(session)
        self.assertEqual(OPTIMIZED_EXPORT_NRE_EXTRA_RECYCLES, 1)
        self.assertEqual(ssh.call_count, 1 + OPTIMIZED_EXPORT_NRE_EXTRA_RECYCLES)
        self.assertEqual(rest.call_count, 1 + OPTIMIZED_EXPORT_NRE_EXTRA_RECYCLES)
        self.assertEqual(
            session._http.get.call_count, OPTIMIZED_EXPORT_NRE_EXTRA_RECYCLES
        )

    def test_kind_reports_optimized_export_nre(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _nre_get()
        live, kind = _inspection_plan_kind(session)
        self.assertFalse(live)
        self.assertEqual(kind, OPTIMIZED_EXPORT_NRE_KIND)

    def test_wait_timeout_reports_optimized_export_nre(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _nre_get()
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.time.sleep"),
            patch(
                "acuqms.publish.time.monotonic",
                side_effect=[0.0, 0.0, 10.0],
            ),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                wait_published(timeout=5.0, poll=1.0)
        self.assertIn(f"last GET {OPTIMIZED_EXPORT_NRE_KIND}", str(ctx.exception))

    def test_entity_200_is_not_qms_live(self) -> None:
        """V20 / B15: wait_rest GET /entity 200 is not InspectionPlan live."""
        rest_src = inspect.getsource(wait_rest)
        live_src = inspect.getsource(qms_endpoint_live)
        self.assertIn("list_endpoints", rest_src)
        self.assertNotIn("InspectionPlan", rest_src)
        self.assertIn("InspectionPlan", live_src)
        src = (ROOT / "acuqms" / "publish.py").read_text(encoding="utf-8")
        body = src[
            src.index("def _recycle_app_pool") : src.index("\ndef qms_setup_insert_sql")
        ]
        self.assertIn("_recycle_if_optimized_export_nre", body)
        self.assertIn("OPTIMIZED_EXPORT_NRE_KIND", body)
        publish_body = src[
            src.index("def publish_package") : src.index("\ndef roles_in_graph_rows")
        ]
        self.assertLess(
            publish_body.index("_recycle_app_pool"),
            publish_body.index("wait_published()"),
        )

    def test_hosted_path_skips_recycle(self) -> None:
        session = MagicMock()
        session._http.get.return_value = _nre_get()
        ssh, rest = self._recycle(session, inst_ssh=None)
        self.assertEqual(ssh.call_count, 0)
        self.assertEqual(rest.call_count, 0)
        session._http.get.assert_not_called()


class TestUnpublishV26(unittest.TestCase):
    def test_remaining_published_keeps_acubootstrap(self) -> None:
        """V26: unpublish merge list keeps AcuBootstrap."""
        self.assertEqual(
            remaining_published([ACUBOOTSTRAP, PACKAGE_NAME]),
            [ACUBOOTSTRAP],
        )
        self.assertEqual(
            remaining_published([PACKAGE_NAME, ACUBOOTSTRAP, "Other"]),
            [ACUBOOTSTRAP, "Other"],
        )
        self.assertEqual(remaining_published([ACUBOOTSTRAP]), [ACUBOOTSTRAP])
        self.assertEqual(remaining_published([PACKAGE_NAME]), [])

    def test_unpublish_publish_begin_merge_false_keeps_acubootstrap(self) -> None:
        session = MagicMock()
        session.customization_published.return_value = [ACUBOOTSTRAP, PACKAGE_NAME]
        session.customization_publish_end.return_value = {"isCompleted": True}
        inst = MagicMock()
        inst.ssh = "Administrator@host"
        inst.tenant = "CNBN"
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin") as begin,
            patch("acuqms.publish.instance", return_value=inst),
            patch("acuqms.publish._drop_unpublish_leftovers") as drop,
            patch("acuqms.publish._drop_unpublish_db_leftovers") as drop_db,
            patch("acuqms.publish._restore_ootb_webpack") as webpack,
            patch("acuqms.publish._recycle_app_pool") as recycle,
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = unpublish_package()
        self.assertEqual(status, "unpublished")
        begin.assert_called_once_with(session, [ACUBOOTSTRAP], merge=False)
        session._http.post.assert_any_call(
            "/CustomizationApi/delete",
            json={"projectName": PACKAGE_NAME},
        )
        drop.assert_called_once()
        drop_db.assert_called_once()
        webpack.assert_called_once()
        recycle.assert_called_once()

    def test_unpublish_empty_remaining_raises(self) -> None:
        session = MagicMock()
        session.customization_published.return_value = [PACKAGE_NAME]
        inst = MagicMock()
        inst.ssh = ""
        inst.tenant = "CNBN"
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin") as begin,
            patch("acuqms.publish.instance", return_value=inst),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                unpublish_package()
        self.assertIn("AcuBootstrap must stay", str(ctx.exception))
        begin.assert_not_called()

    def test_unpublish_no_ssh_skips_filesystem_and_documents(self) -> None:
        session = MagicMock()
        session.customization_published.return_value = [ACUBOOTSTRAP, PACKAGE_NAME]
        session.customization_publish_end.return_value = {"isCompleted": True}
        inst = MagicMock()
        inst.ssh = ""
        inst.tenant = "CNBN"
        err = io.StringIO()
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin") as begin,
            patch("acuqms.publish.instance", return_value=inst),
            patch("acuqms.publish._drop_unpublish_leftovers") as drop,
            patch("acuqms.publish._restore_ootb_webpack") as webpack,
            patch("acuqms.publish._recycle_app_pool") as recycle,
            patch("acuqms.progress.sys.stderr", err),
        ):
            status = unpublish_package()
        self.assertEqual(status, "unpublished")
        begin.assert_called_once_with(session, [ACUBOOTSTRAP], merge=False)
        drop.assert_not_called()
        webpack.assert_not_called()
        recycle.assert_not_called()
        rows = parse_progress(err.getvalue())
        skip = [row for row in rows if row[0] == "filesystem delete and pool recycle"]
        self.assertEqual(len(skip), 1)
        self.assertEqual(skip[0][1], "ACU_SSH required")
        self.assertEqual(skip[0][2], "skip")

    def test_import_after_unpublish_does_not_digest_skip(self) -> None:
        """V18 / V26: after unpublish, Lab5.QMS is not live → import, not skip."""
        zip_bytes = _tiny_zip()
        desc = package_description(zip_bytes)
        session = _session_with_plan(plan_status=404)
        session.customization_published.return_value = [ACUBOOTSTRAP]
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin") as begin,
            patch("acuqms.publish.wait_published") as wait,
            patch("acuqms.publish.published_description", return_value=desc),
            patch("acuqms.publish._ensure_webpack_no_color", return_value=False),
            patch(
                "acuqms.publish._remove_file_item_frontend_leftovers",
                return_value=False,
            ),
            patch(
                "acuqms.publish._webpack_tenant_screens_missing",
                return_value=False,
            ),
            patch("acuqms.publish._ensure_qms_detail_mappings", return_value=0),
            patch("acuqms.publish._ensure_qm_aspx_pages"),
            patch("acuqms.publish._recycle_app_pool"),
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = publish_package(zip_bytes)
        self.assertEqual(status, "published")
        session.customization_import.assert_called_once()
        begin.assert_called_once_with(session, [PACKAGE_NAME], replay=True)
        wait.assert_called_once_with()

    def test_unpublish_source_never_unpublish_all_or_cache_wipe(self) -> None:
        src = (ROOT / "acuqms" / "publish.py").read_text(encoding="utf-8")
        body = src[
            src.index("def unpublish_package") : src.index(
                "\ndef _webpack_tenant_screens_missing"
            )
        ]
        self.assertNotIn("/CustomizationApi/unpublishAll", src)
        self.assertNotIn('unpublishAll"', src)
        self.assertNotIn("unpublishAll'", src)
        self.assertIn("merge=False", body)
        self.assertIn("/CustomizationApi/delete", src)
        self.assertIn("def _delete_unpublished_project", src)
        self.assertIn("Pages/QM", body)
        self.assertIn("customizationScreens", body)
        self.assertIn("IN202500_QMS", body)
        self.assertIn("src/screens", body)
        self.assertIn(r"Scripts\\Screens", body)
        self.assertNotIn("& $npm run build", body)
        self.assertNotIn("npm.cmd", body)
        self.assertIn("GenericInquiry", body)
        self.assertIn("OOTB_WEBPACK_REFERENCE", body)
        self.assertIn(f"{OOTB_WEBPACK_REFERENCE}", src)
        self.assertIn("def restore_ootb_webpack_ps1", src)
        self.assertNotIn("StateCache", body)
        self.assertNotIn("Temporary ASP.NET", body)
        self.assertNotIn("InventoryItem", body)
        help_r = CliRunner().invoke(cli, ["unpublish", "--help"])
        self.assertEqual(help_r.exit_code, 0, help_r.output)
        self.assertIn("ACU_SSH", help_r.output)
        self.assertIn("CustomizationApi", help_r.output)

    def test_unpublish_db_sql_drops_sitemap_and_endpoint_not_stock(self) -> None:
        sql = unpublish_db_leftover_sql(3)
        self.assertIn("DELETE FROM", sql)
        self.assertIn("SiteMap", sql)
        self.assertIn("EntityDescription", sql)
        self.assertIn("EntityEndpoint", sql)
        self.assertIn("MUIScreen", sql)
        self.assertIn("InterfaceName = N'QMS'", sql)
        self.assertIn("ScreenID LIKE N'QM%'", sql)
        self.assertIn("CompanyID IN (1, @cid)", sql)
        self.assertNotIn("InventoryItem", sql)
        self.assertNotIn("UsrQMS", sql)

    def test_restore_ootb_webpack_ps1_keeps_site_vendor(self) -> None:
        """V26 / B16: restore GenericInquiry to IN202000 vendor; never npm production."""
        ps1 = restore_ootb_webpack_ps1(r"C:\Acumatica\AcumaticaERP", "CNBN")
        self.assertIn("GenericInquiry", ps1)
        self.assertIn("IN202500", ps1)
        self.assertIn(OOTB_WEBPACK_REFERENCE + ".html", ps1)
        for name in SHARED_WEBPACK_SCREENS:
            self.assertIn("'" + name + "'", ps1, name)
        self.assertNotIn("npm run build", ps1)
        self.assertNotIn("npm.cmd", ps1)
        self.assertNotIn("screenIds=IN202500", ps1)
        self.assertNotIn("--env production", ps1)
        self.assertIn("Sort-Object LastWriteTime", ps1)

    def test_unpublish_delete_transport_error_still_drops_leftovers(self) -> None:
        """V26: publishEnd recycle must not skip leftover drop or delete retry."""
        session = MagicMock()
        session.customization_published.return_value = [ACUBOOTSTRAP, PACKAGE_NAME]
        session.customization_publish_end.return_value = {"isCompleted": True}
        session._http.post.side_effect = [
            httpx.TransportError("reset"),
            MagicMock(),
        ]
        inst = MagicMock()
        inst.ssh = "Administrator@host"
        inst.tenant = "CNBN"
        with (
            patch("acuqms.publish.client", return_value=_session_ctx(session)),
            patch("acuqms.publish.drain_publish"),
            patch("acuqms.publish.publish_begin"),
            patch("acuqms.publish.instance", return_value=inst),
            patch("acuqms.publish._drop_unpublish_leftovers") as drop,
            patch("acuqms.publish._drop_unpublish_db_leftovers") as drop_db,
            patch("acuqms.publish._restore_ootb_webpack") as webpack,
            patch("acuqms.publish._recycle_app_pool") as recycle,
            patch("acuqms.progress.sys.stderr", io.StringIO()),
        ):
            status = unpublish_package()
        self.assertEqual(status, "unpublished")
        session.relogin.assert_called()
        drop.assert_called_once()
        drop_db.assert_called_once()
        webpack.assert_called_once()
        recycle.assert_called_once()

    def test_cli_unpublish_stdout_unpublished(self) -> None:
        with patch(
            "acuqms.cli.publish.unpublish_package", return_value="unpublished"
        ) as unpub:
            r = CliRunner().invoke(cli, ["unpublish"])
        self.assertEqual(r.exit_code, 0, r.output)
        unpub.assert_called_once_with(timeout=900.0)
        self.assertEqual(r.stdout.strip(), "unpublished")
        self.assertNotIn("\t", r.stdout)


class TestPackModuleZipBytesV8(unittest.TestCase):
    def test_package_zip_name_constant(self) -> None:
        from acuqms import pack

        self.assertEqual(pack.PACKAGE_ZIP, "Lab5_QMS_Customization.zip")
        self.assertEqual(pack.ASSEMBLY_DLL, "Lab5.QMS.dll")
        with zipfile.ZipFile(io.BytesIO(pack.package_zip(ROOT))) as zf:
            self.assertIn("project.xml", zf.namelist())


if __name__ == "__main__":
    unittest.main()
