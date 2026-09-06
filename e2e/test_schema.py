#!/usr/bin/env -S uv run
"""SSH sqlcmd: UsrQMS tables, InventoryItem usr columns, QM sitemap."""

from __future__ import annotations

import unittest

from e2e.helper import (
    ACCESSRIGHTS_DELETE,
    DB_NAME,
    QUALITY_MANAGER_ROLE,
    QM_SCREENS,
    ROLES_IN_GRAPH_APPLICATION,
    USR_ITEM_COLUMNS,
    USR_QMS_TABLES,
    bootstrap_endpoint,
    client,
    company_id,
    ensure_numbering_and_role,
    ensure_published,
    instance,
    roles_in_graph_company_ids,
    roles_in_graph_rows,
    sql_lines,
)


class TestSqlSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not instance().ssh:
            raise unittest.SkipTest("hosted path (blank ACU_SSH) — no sqlcmd")
        ensure_published()

    def test_usrqms_tables(self) -> None:
        names = set(
            sql_lines(
                f"SELECT TABLE_NAME FROM {DB_NAME}.INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_NAME LIKE 'UsrQMS%' ORDER BY TABLE_NAME"
            )
        )
        missing = [table for table in USR_QMS_TABLES if table not in names]
        self.assertEqual(missing, [], f"missing UsrQMS tables: {missing}")

    def test_inventory_item_usr_columns(self) -> None:
        cols = set(
            sql_lines(
                f"SELECT COLUMN_NAME FROM {DB_NAME}.INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = 'InventoryItem' AND ("
                "COLUMN_NAME LIKE 'UsrQMS%' OR COLUMN_NAME LIKE 'UsrMinShelf%')"
            )
        )
        missing = [col for col in USR_ITEM_COLUMNS if col not in cols]
        self.assertEqual(missing, [], f"missing InventoryItem usr columns: {missing}")

    def test_sitemap_qm_screens(self) -> None:
        cid = company_id()
        screens = set(
            sql_lines(
                f"SELECT DISTINCT ScreenID FROM {DB_NAME}.dbo.SiteMap "
                f"WHERE ScreenID LIKE 'QM%' AND CompanyID IN (1, {cid}) "
                "ORDER BY ScreenID"
            )
        )
        missing = [screen for screen in QM_SCREENS if screen not in screens]
        self.assertEqual(missing, [], f"missing QM sitemap screens: {missing}")
        self.assertIn("QM000000", screens)


class TestBootstrapNumberingAndRole(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            try:
                ensure_numbering_and_role(session)
            except RuntimeError as exc:
                raise unittest.SkipTest(f"numbering/role seed: {exc}") from exc

    def test_qord_qncr_and_quality_manager(self) -> None:
        ids = set(
            sql_lines(
                f"SELECT NumberingID FROM {DB_NAME}.dbo.Numbering "
                "WHERE NumberingID IN ('QORD', 'QNCR')"
            )
        )
        self.assertIn("QORD", ids)
        self.assertIn("QNCR", ids)
        with client() as session:
            boot = bootstrap_endpoint(session)
            role = session.get_record("Role", [QUALITY_MANAGER_ROLE], endpoint=boot)
        self.assertIsNotNone(role)

    def test_roles_in_graph_delete_on_qm_screens(self) -> None:
        expected = {
            (cid, role, screen, ACCESSRIGHTS_DELETE)
            for cid in roles_in_graph_company_ids()
            for role, screen in roles_in_graph_rows()
        }
        rows = {
            (int(cid), role, screen, int(rights))
            for line in sql_lines(
                "SELECT CompanyID, Rolename, ScreenID, Accessrights FROM "
                f"{DB_NAME}.dbo.RolesInGraph WHERE ApplicationName = "
                f"N'{ROLES_IN_GRAPH_APPLICATION}' AND ScreenID IN ("
                + ", ".join(f"N'{screen}'" for screen in QM_SCREENS)
                + ")"
            )
            for cid, role, screen, rights in [line.split("|")]
        }
        self.assertTrue(
            expected.issubset(rows),
            f"missing RolesInGraph Delete rows: {sorted(expected - rows)}",
        )

    def test_acu_user_has_quality_manager(self) -> None:
        user = instance().user.replace("'", "''")
        attached = {
            int(cid)
            for line in sql_lines(
                "SELECT CompanyID FROM "
                f"{DB_NAME}.dbo.UsersInRoles WHERE Username = N'{user}' "
                f"AND Rolename = N'{QUALITY_MANAGER_ROLE}' "
                f"AND ApplicationName = N'{ROLES_IN_GRAPH_APPLICATION}'"
            )
            for cid in [line]
        }
        missing = [cid for cid in roles_in_graph_company_ids() if cid not in attached]
        self.assertEqual(
            missing,
            [],
            f"{instance().user!r} missing {QUALITY_MANAGER_ROLE} on {missing}",
        )


if __name__ == "__main__":
    unittest.main()
