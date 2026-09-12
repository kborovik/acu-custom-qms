#!/usr/bin/env -S uv run
"""T58 / V26 / V18: unpublish Lab5.QMS only, then deploy imports again."""

from __future__ import annotations

import unittest

from e2e import helper
from e2e.helper import (
    DB_NAME,
    ITEM_CD,
    PACKAGE_NAME,
    QMS_ENDPOINT,
    QMS_VERSION,
    client,
    company_id,
    ensure_published,
    instance,
    sql_lines,
)
from acuqms.acu import ACU_INSTANCE_PATH, ssh_run
from acuqms.publish import (
    ACUBOOTSTRAP,
    _inspection_plan_kind,
    unpublish_package,
)


def _path_exists(path: str) -> bool:
    literal = path.replace("'", "''")
    out = ssh_run(
        "if (Test-Path -LiteralPath '" + literal + "') { 'YES' } else { 'NO' }"
    )
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return (lines[-1] if lines else "") == "YES"


class TestUnpublishLab5OnlyV26(unittest.TestCase):
    restored = False

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        cls.status = unpublish_package()
        helper._published = None
        helper._publish_error = None

    @classmethod
    def tearDownClass(cls) -> None:
        helper._published = None
        helper._publish_error = None
        try:
            ensure_published()
            cls.restored = True
        except BaseException:
            pass

    def test_unpublish_status(self) -> None:
        self.assertEqual(self.status, "unpublished")

    def test_get_published_omits_lab5_keeps_acubootstrap(self) -> None:
        with client() as session:
            names = session.customization_published()
        self.assertNotIn(PACKAGE_NAME, names)
        self.assertIn(ACUBOOTSTRAP, names)

    def test_entity_omits_qms(self) -> None:
        with client() as session:
            endpoints = session.list_endpoints()
        self.assertNotIn(("QMS", QMS_VERSION), endpoints)

    def test_inspection_plan_not_200_json_array(self) -> None:
        with client() as session:
            live, _kind = _inspection_plan_kind(session)
        self.assertFalse(live)

    def test_leftovers_gone(self) -> None:
        inst = instance()
        if not inst.ssh:
            raise unittest.SkipTest("ACU_SSH empty — no leftover filesystem probe")
        tenant = inst.tenant
        root = ACU_INSTANCE_PATH
        leftover = [
            root + r"\Pages\QM",
            root + r"\FrontendSources\screen\src\screens\QM",
            root + r"\FrontendSources\screen\src\screens\IN\IN202500"
            r"\extensions\IN202500_QMS.html",
            root + r"\FrontendSources\screen\src\screens\IN\IN202500"
            r"\extensions\IN202500_QMS.ts",
            root + rf"\FrontendSources\screen\src\customizationScreens\{tenant}",
            root + rf"\Scripts\Screens\{tenant}\QM101000.html",
            root + rf"\Scripts\Screens\{tenant}\QM201000.html",
            root + rf"\Scripts\Screens\{tenant}\QM301000.html",
            root + rf"\Scripts\Screens\{tenant}\QM302000.html",
        ]
        present = [path for path in leftover if _path_exists(path)]
        self.assertEqual(present, [], f"unpublish leftovers still on disk: {present}")

    def test_in202500_without_usrqms(self) -> None:
        if not instance().ssh:
            raise unittest.SkipTest("ACU_SSH empty — webpack not rebuilt")
        tenant = instance().tenant
        with client() as session:
            compiled = session._http.get(f"/Scripts/Screens/{tenant}/IN202500.html")
            if compiled.status_code == 404:
                compiled = session._http.get("/Scripts/Screens/IN202500.html")
            self.assertEqual(
                compiled.status_code,
                200,
                f"IN202500 compiled html -> {compiled.status_code}",
            )
            html = compiled.text
            self.assertNotIn("UsrQMSInspectionRequired", html)
            self.assertNotIn("UsrQMSInspectionPlanID", html)
            bundle_name = None
            for token in html.replace("'", '"').split('"'):
                if token.startswith("IN202500.") and token.endswith(".bundle.js"):
                    bundle_name = token
                    break
            if bundle_name:
                bundle = session._http.get(f"/Scripts/Screens/{tenant}/{bundle_name}")
                if bundle.status_code == 404:
                    bundle = session._http.get(f"/Scripts/Screens/{bundle_name}")
                self.assertEqual(bundle.status_code, 200, bundle_name)
                js = bundle.text
                self.assertNotIn("UsrQMSInspectionRequired", js)
                self.assertNotIn("InventoryItem_QMS", js)
            screen = session._checked(
                session._http.get(
                    "/Main",
                    params={"ScreenId": "IN202500"},
                    follow_redirects=True,
                )
            )
        url = str(screen.url)
        self.assertTrue(
            "ScreenId=IN202500" in url or "ScreenID=IN202500" in url,
            f"IN202500 dropped from url after redirects: {url}",
        )

    def test_navbar_inspection_zero(self) -> None:
        inst = instance()
        if not inst.ssh:
            raise unittest.SkipTest("ACU_SSH empty — no SiteMap sqlcmd")
        cid = company_id()
        rows = sql_lines(
            "SELECT ScreenID, Title FROM "
            f"{DB_NAME}.dbo.SiteMap WHERE CompanyID IN (1, {cid}) AND "
            "ScreenID LIKE N'QM%'"
        )
        self.assertEqual(rows, [], f"navbar Inspection still listed: {rows}")

    def test_stock_items_stay(self) -> None:
        with client() as session:
            items = session.get_list("StockItem", {"$top": "8"})
            self.assertIsInstance(items, list)
            self.assertGreaterEqual(
                len(items),
                1,
                "Stock Items GI blank after unpublish",
            )
            named = session.get_record("StockItem", [ITEM_CD])
        if named is None:
            raise unittest.SkipTest(
                f"StockItem {ITEM_CD} missing — seed tenant from acu-gitops-qms"
            )

    def test_zz_subsequent_deploy_imports(self) -> None:
        helper._published = None
        helper._publish_error = None
        status = ensure_published()
        self.assertEqual(status, "published")
        with client() as session:
            self.assertTrue(helper.qms_endpoint_live(session))
            self.assertIn(PACKAGE_NAME, session.customization_published())
            self.assertIn(("QMS", QMS_VERSION), session.list_endpoints())
            response = session._http.get(f"/entity/{QMS_ENDPOINT}/InspectionPlan")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        TestUnpublishLab5OnlyV26.restored = True


if __name__ == "__main__":
    unittest.main()
