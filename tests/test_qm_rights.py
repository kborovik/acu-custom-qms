#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T13 / V10 / V8: post-publish QM RolesInGraph seed; zip excludes Role rows."""

from __future__ import annotations

import hashlib
import io
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from e2e.helper import (  # noqa: E402
    ACCESSRIGHTS_DELETE,
    QUALITY_MANAGER_ROLE,
    QM_RIGHTS_ROLES,
    QM_SCREENS,
    ROLES_IN_GRAPH_APPLICATION,
    ROLES_IN_GRAPH_COMPANY_ID,
    roles_in_graph_merge_sql,
    roles_in_graph_rows,
)
from lab5_qms import publish as publish_mod  # noqa: E402
from lab5_qms.publish import (  # noqa: E402
    QMS_DETAIL_MAPPINGS,
    _ensure_qm_aspx_pages,
    _parse_mapping_seed_counts,
    _qm_aspx_names,
    expected_qms_detail_mapping_count,
    qms_detail_mapping_sql,
    seed_qm_rights,
    sitemap_selected_ui_sql,
    zip_digest,
)

HELPER = ROOT / "e2e" / "helper.py"
PUBLISH = ROOT / "lab5_qms" / "publish.py"
PACKAGE_E2E = ROOT / "e2e" / "test_package.py"
FUNCTIONAL_E2E = ROOT / "e2e" / "test_functional.py"


class TestRolesInGraphSeedV10(unittest.TestCase):
    def test_rows_cover_admin_and_quality_manager_on_qm_screens(self) -> None:
        rows = roles_in_graph_rows()
        self.assertEqual(QM_RIGHTS_ROLES, ("Administrator", QUALITY_MANAGER_ROLE))
        self.assertEqual(
            set(rows),
            {(role, screen) for role in QM_RIGHTS_ROLES for screen in QM_SCREENS},
        )
        self.assertEqual(len(rows), 10)
        self.assertIn("QM401000", QM_SCREENS)
        self.assertEqual(ROLES_IN_GRAPH_COMPANY_ID, 1)
        self.assertEqual(ROLES_IN_GRAPH_APPLICATION, "/")
        self.assertEqual(ACCESSRIGHTS_DELETE, 4)

    def test_merge_sql_delete_rights_company_id_1(self) -> None:
        sql = roles_in_graph_merge_sql()
        self.assertIn("MERGE", sql)
        self.assertIn("RolesInGraph", sql)
        self.assertIn("Accessrights", sql)
        self.assertIn(str(ACCESSRIGHTS_DELETE), sql)
        self.assertIn(f"CompanyID = {ROLES_IN_GRAPH_COMPANY_ID}", sql)
        self.assertIn(f"({ROLES_IN_GRAPH_COMPANY_ID}, N'", sql)
        for role, screen in roles_in_graph_rows():
            self.assertIn(f"N'{screen}'", sql, screen)
            self.assertIn(f"N'{role}'", sql, role)

    def test_merge_sql_includes_tenant_company_when_given(self) -> None:
        sql = roles_in_graph_merge_sql((ROLES_IN_GRAPH_COMPANY_ID, 14))
        self.assertIn("(1, N'QM201000', N'Administrator'", sql)
        self.assertIn("(14, N'QM201000', N'Administrator'", sql)
        self.assertIn("(14, N'QM201000', N'Quality Manager'", sql)

    def test_zip_digest_covers_all_members(self) -> None:
        def blob(**members: bytes) -> bytes:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                for name, body in members.items():
                    zf.writestr(name, body)
            return buf.getvalue()

        base = {
            "project.xml": b"<Customization/>",
            "Bin/Lab5.QMS.dll": b"MZ",
            "FrontendSources/screen/src/screens/QM/QM301000/QM301000.html": b"old-page",
            "Scripts/CreateQMSTables.sql": b"CREATE TABLE",
        }
        same = zip_digest(blob(**base))
        self.assertEqual(same, zip_digest(blob(**base)))
        self.assertNotEqual(
            same,
            zip_digest(
                blob(
                    **{
                        **base,
                        "FrontendSources/screen/src/screens/QM/QM301000/QM301000.html": b"new-page",
                    }
                )
            ),
        )
        self.assertNotEqual(
            same,
            zip_digest(blob(**{**base, "Bin/Lab5.QMS.dll": b"MZ2"})),
        )
        self.assertNotEqual(
            same,
            zip_digest(blob(**{**base, "Scripts/CreateQMSTables.sql": b"ALTER"})),
        )
        src = PUBLISH.read_text(encoding="utf-8")
        self.assertIn("for name in sorted(zf.namelist())", src)
        self.assertNotIn('dll_name = "Bin/" + pack.ASSEMBLY_DLL', src)

    def test_ensure_published_seeds_qm_rights(self) -> None:
        src = HELPER.read_text(encoding="utf-8")
        publish = PUBLISH.read_text(encoding="utf-8")
        self.assertIn("ensure_qm_rights(session)", src)
        self.assertIn("def ensure_qm_rights", src)
        self.assertIn("_ensure_acu_user_quality_manager", src)
        self.assertIn("seed_qm_rights(session)", src)
        self.assertIn("def seed_qm_rights", publish)
        self.assertIn("_ensure_qm_roles_in_graph", publish)
        self.assertIn("roles_in_graph_company_ids()", publish)
        self.assertIn("_ensure_qms_detail_mappings", publish)
        self.assertIn("_recycle_app_pool", publish)
        self.assertIn("_ensure_qms_setup_rows", publish)
        self.assertIn("qms_setup_insert_sql", publish)
        self.assertIn("_ensure_qm_selected_ui", publish)
        self.assertIn("_remove_file_item_frontend_leftovers", publish)
        self.assertIn("_ensure_webpack_no_color", publish)
        self.assertIn("_webpack_tenant_screens_missing", publish)
        self.assertIn("wait_rest", publish)
        self.assertNotIn("SetEnvironmentVariable", publish)
        self.assertNotIn("Start-Sleep", publish)
        self.assertIn("PerTenantFile", (ROOT / "lab5_qms" / "pack.py").read_text())

    def test_sitemap_selected_ui_sql_clears_classic_lock(self) -> None:
        sql = sitemap_selected_ui_sql()
        self.assertIn("SelectedUI = N'D'", sql)
        self.assertIn("N'QM301000'", sql)
        self.assertIn("SelectedUI <> N'D'", sql)


class TestQmsDetailMappingSeedV12(unittest.TestCase):
    def test_merge_sql_covers_plan_and_order_fields(self) -> None:
        sql = qms_detail_mapping_sql(14)
        self.assertIn("MERGE", sql)
        self.assertIn("EntityMapping", sql)
        self.assertIn("InterfaceName = N'QMS'", sql)
        self.assertIn("CompanyID IN (@cid, 1)", sql)
        self.assertIn("InspectionPlan", sql)
        self.assertIn("InspectionOrder", sql)
        self.assertIn("N'Tests'", sql)
        self.assertIn("N'Results'", sql)
        for parent, collection, detail, fields in QMS_DETAIL_MAPPINGS:
            self.assertIn(f"N'{parent}'", sql, parent)
            self.assertIn(f"N'{collection}'", sql, collection)
            self.assertIn(f"N'{detail}'", sql, detail)
            for name in fields:
                self.assertIn(f"N'{name}'", sql, name)
        self.assertEqual(expected_qms_detail_mapping_count(), 17)

    def test_mapping_seed_recycles_when_maps_were_missing(self) -> None:
        session = MagicMock()
        with (
            patch(
                "lab5_qms.publish.bootstrap_endpoint",
                return_value="Bootstrap/1.4.0",
            ),
            patch("lab5_qms.publish._ensure_quality_manager_role_row"),
            patch("lab5_qms.publish._ensure_qm_roles_in_graph"),
            patch("lab5_qms.publish._ensure_qms_detail_mappings", return_value=1),
            patch("lab5_qms.publish._ensure_qms_setup_rows"),
            patch("lab5_qms.publish._ensure_quality_queue_gi"),
            patch("lab5_qms.publish._ensure_qm_aspx_pages"),
            patch("lab5_qms.publish._ensure_qm_selected_ui"),
            patch("lab5_qms.publish._recycle_app_pool") as recycle,
        ):
            seed_qm_rights(session)
        recycle.assert_called_once()

    def test_mapping_seed_skips_recycle_when_maps_present(self) -> None:
        session = MagicMock()
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
            patch("lab5_qms.publish._recycle_app_pool") as recycle,
        ):
            seed_qm_rights(session)
        recycle.assert_not_called()

    def test_parse_mapping_counts_rejects_non_int(self) -> None:
        self.assertEqual(_parse_mapping_seed_counts("0|17|17\n"), (0, 17, 17))
        with self.assertRaises(RuntimeError):
            _parse_mapping_seed_counts("ok")
        with self.assertRaises(RuntimeError):
            _parse_mapping_seed_counts("")


class TestAspxPagesSeed(unittest.TestCase):
    def setUp(self) -> None:
        publish_mod._aspx_pages_ready = False

    def tearDown(self) -> None:
        publish_mod._aspx_pages_ready = False

    def test_skips_scp_when_remote_hash_matches(self) -> None:
        names = _qm_aspx_names()
        self.assertEqual(len(names), 8)
        lines = []
        for name in names:
            digest = hashlib.sha256((ROOT / "Pages_QM" / name).read_bytes()).hexdigest()
            lines.append(f"{name}|{digest}")
        inst = MagicMock()
        inst.ssh = "Administrator@host"
        with (
            patch("lab5_qms.publish.instance", return_value=inst),
            patch("lab5_qms.publish.ssh_run", return_value="\n".join(lines)) as ssh,
            patch("lab5_qms.publish.subprocess.run") as scp,
        ):
            _ensure_qm_aspx_pages()
            _ensure_qm_aspx_pages()
        scp.assert_not_called()
        self.assertEqual(ssh.call_count, 1)

    def test_scps_when_remote_missing(self) -> None:
        names = _qm_aspx_names()
        lines = "\n".join(f"{name}|missing" for name in names)
        inst = MagicMock()
        inst.ssh = "Administrator@host"
        scp_ok = MagicMock()
        scp_ok.returncode = 0
        scp_ok.stdout = ""
        scp_ok.stderr = ""
        with (
            patch("lab5_qms.publish.instance", return_value=inst),
            patch("lab5_qms.publish.ssh_run", return_value=lines),
            patch("lab5_qms.publish.subprocess.run", return_value=scp_ok) as scp,
        ):
            _ensure_qm_aspx_pages()
        self.assertEqual(scp.call_count, 8)
        self.assertTrue(publish_mod._aspx_pages_ready)

    def test_dock_lot_skips_before_seed(self) -> None:
        src = FUNCTIONAL_E2E.read_text(encoding="utf-8")
        start = src.index("class TestDockLot")
        end = src.index("class TestPostNcr")
        dock = src[start:end]
        skip_at = dock.index("unittest.SkipTest")
        seed_at = dock.index("ensure_numbering_and_role")
        self.assertGreater(seed_at, skip_at)


class TestNoInspectionPlan403SkipV10(unittest.TestCase):
    def test_package_entity_list_does_not_skip_403(self) -> None:
        src = PACKAGE_E2E.read_text(encoding="utf-8")
        self.assertNotIn("skipTest", src)
        self.assertNotIn("insufficient rights", src)

    def test_functional_plan_put_does_not_skip_403(self) -> None:
        src = FUNCTIONAL_E2E.read_text(encoding="utf-8")
        self.assertNotIn("InspectionPlan PUT unavailable", src)
        skipped = [
            line
            for line in src.splitlines()
            if "skipTest" in line and ("403" in line or "PUT unavailable" in line)
        ]
        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
