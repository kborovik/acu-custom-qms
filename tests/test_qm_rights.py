#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T13 / V10 / V8: post-publish QM RolesInGraph seed; zip excludes Role rows."""

from __future__ import annotations

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
from lab5_qms.publish import (  # noqa: E402
    QMS_DETAIL_MAPPINGS,
    _parse_mapping_seed_counts,
    expected_qms_detail_mapping_count,
    qms_detail_mapping_sql,
    seed_qm_rights,
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
        self.assertEqual(len(rows), 8)
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
            "Pages/QM/QM301000.aspx": b"old-page",
            "Scripts/CreateQMSTables.sql": b"CREATE TABLE",
        }
        same = zip_digest(blob(**base))
        self.assertEqual(same, zip_digest(blob(**base)))
        self.assertNotEqual(
            same,
            zip_digest(blob(**{**base, "Pages/QM/QM301000.aspx": b"new-page"})),
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
