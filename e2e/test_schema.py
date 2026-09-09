#!/usr/bin/env -S uv run
"""SSH sqlcmd: UsrQMS tables, InventoryItem usr columns, QM sitemap / workspace."""

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

QM_WORKSPACE_TITLE = "Inventory"
QM_SEARCH_TITLES = {
    "QM101000": "Quality Preferences",
    "QM201000": "Inspection Plans",
    "QM301000": "Inspection Orders",
    "QM302000": "Non-Conformance Reports",
    "QM401000": "Quality Queue",
}


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
        expected = set(QM_SCREENS) | set(QM_SEARCH_TITLES)
        missing = [screen for screen in expected if screen not in screens]
        self.assertEqual(missing, [], f"missing QM sitemap screens: {missing}")
        self.assertNotIn("QM000000", screens)

    def test_sitemap_qm_workspaces(self) -> None:
        cid = company_id()
        sitemap_cols = {
            line.split("|")[0]
            for line in sql_lines(
                f"SELECT COLUMN_NAME FROM {DB_NAME}.INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = 'SiteMap'"
            )
        }
        mui_tables = {
            line
            for line in sql_lines(
                f"SELECT TABLE_NAME FROM {DB_NAME}.INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_NAME IN ('MUIWorkspace', 'MUIScreen', 'PortalMap')"
            )
        }
        self.assertIn("MUIWorkspace", mui_tables)
        self.assertIn("MUIScreen", mui_tables)
        self.assertNotIn("Workspaces", sitemap_cols)
        assigned = {}
        screen_ids = tuple(QM_SEARCH_TITLES)
        for line in sql_lines(
            "SELECT sm.ScreenID, w.Title FROM "
            f"{DB_NAME}.dbo.SiteMap sm "
            f"INNER JOIN {DB_NAME}.dbo.MUIScreen ms ON ms.NodeID = sm.NodeID "
            f"INNER JOIN {DB_NAME}.dbo.MUIWorkspace w "
            "ON w.WorkspaceID = ms.WorkspaceID "
            "WHERE sm.ScreenID IN ("
            + ", ".join(f"N'{screen}'" for screen in screen_ids)
            + f") AND sm.CompanyID IN (1, {cid})"
        ):
            screen, title = line.split("|", 1)
            assigned[screen] = title
        missing = [
            screen
            for screen in screen_ids
            if assigned.get(screen) != QM_WORKSPACE_TITLE
        ]
        self.assertEqual(
            missing,
            [],
            f"Site Map Workspaces not Inventory: {missing} ({assigned})",
        )
        self.assertNotIn("Configuration", set(assigned.values()))
        qms_workspace = sql_lines(
            f"SELECT Title, ScreenID FROM {DB_NAME}.dbo.MUIWorkspace "
            "WHERE Title = N'Quality Management' "
            f"AND CompanyID IN (1, {cid})"
        )
        self.assertEqual(
            qms_workspace,
            [],
            f"QMS MUIWorkspace still present: {qms_workspace}",
        )
        sitemap_folder = sql_lines(
            f"SELECT ScreenID FROM {DB_NAME}.dbo.SiteMap "
            f"WHERE ScreenID = N'QM000000' AND CompanyID IN (1, {cid})"
        )
        self.assertEqual(
            sitemap_folder,
            [],
            f"SiteMap QM000000 still present: {sitemap_folder}",
        )


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


def _workspace_screens(payload: dict, title: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for workspace in payload.get("workspaces") or []:
        if not isinstance(workspace, dict):
            continue
        if workspace.get("title") != title:
            continue
        for category in workspace.get("subcategories") or []:
            if not isinstance(category, dict):
                continue
            for screen in category.get("screens") or []:
                if not isinstance(screen, dict):
                    continue
                screen_id = screen.get("screenID")
                screen_title = screen.get("title")
                if isinstance(screen_id, str) and isinstance(screen_title, str):
                    found[screen_id] = screen_title
    return found


class TestModernQmWorkspace(unittest.TestCase):
    """T37 / V16: Inventory-hosted QM screens; no QMS tile; no Configuration."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()

    def test_frameset_sitemap_inventory(self) -> None:
        with client() as session:
            response = session._checked(session._http.get("/frameset/sitemap"))
        payload = response.json()
        workspaces = payload.get("workspaces") or []
        titles = [
            workspace.get("title")
            for workspace in workspaces
            if isinstance(workspace, dict)
        ]
        self.assertIn(
            QM_WORKSPACE_TITLE,
            titles,
            f"Inventory missing from workspace bar/More Items: {titles}",
        )
        self.assertNotIn("Quality Management", titles)
        assigned = _workspace_screens(payload, QM_WORKSPACE_TITLE)
        missing = [
            f"{screen_id} {title}"
            for screen_id, title in QM_SEARCH_TITLES.items()
            if assigned.get(screen_id) != title
        ]
        self.assertEqual(
            missing,
            [],
            f"Search/menu missing QM screens under {QM_WORKSPACE_TITLE}: "
            f"{missing} ({assigned})",
        )
        self.assertNotIn("QM000000", assigned)
        configuration = _workspace_screens(payload, "Configuration")
        leaked = [
            screen_id for screen_id in QM_SEARCH_TITLES if screen_id in configuration
        ]
        self.assertEqual(
            leaked,
            [],
            f"Configuration lists QM screens: {leaked} ({configuration})",
        )

    def test_screenid_urls_keep_working(self) -> None:
        with client() as session:
            for screen_id in QM_SCREENS:
                response = session._checked(
                    session._http.get(
                        "/Main",
                        params={"ScreenId": screen_id},
                        follow_redirects=True,
                    )
                )
                url = str(response.url)
                self.assertTrue(
                    f"ScreenId={screen_id}" in url or f"ScreenID={screen_id}" in url,
                    f"{screen_id} dropped from url after redirects: {url}",
                )


if __name__ == "__main__":
    unittest.main()
