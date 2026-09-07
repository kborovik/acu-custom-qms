#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T13 / V10 / V8: post-publish QM RolesInGraph seed; zip excludes Role rows."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

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

    def test_publish_digest_includes_dll(self) -> None:
        src = PUBLISH.read_text(encoding="utf-8")
        self.assertIn("digest.update(zf.read(\"project.xml\"))", src)
        self.assertIn('dll_name = "Bin/" + pack.ASSEMBLY_DLL', src)
        self.assertIn("digest.update(zf.read(dll_name))", src)

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
        self.assertIn("E/{parent}/{collectionField}/{detail}/{field}", publish)


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
            if "skipTest" in line
            and ("403" in line or "PUT unavailable" in line)
        ]
        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
