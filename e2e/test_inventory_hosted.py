#!/usr/bin/env -S uv run
"""T37 / V16 / V17: Inventory-hosted Modern UI, Quality Queue GI, package shape."""

from __future__ import annotations

import io
import unittest
import zipfile
import xml.etree.ElementTree as ET

from e2e.helper import (
    DB_NAME,
    PACKAGE_NAME,
    ROOT,
    client,
    company_id,
    ensure_numbering_and_role,
    ensure_published,
    instance,
    qms_put,
    sql_lines,
)
from acuqms import pack
from acuqms.acu import ACU_INSTANCE_PATH, ssh_run
from acuqms.publish import ACCESSRIGHTS_DELETE, QM_RIGHTS_ROLES

GI_DESIGN_ID = "9f9483b9-6427-40c6-9c91-96b22c67c28e"
PATTERN_B = (
    "screens/QM/QM101000/QM101000.ts",
    "screens/QM/QM201000/QM201000.ts",
    "screens/QM/QM301000/QM301000.ts",
    "screens/QM/QM302000/QM302000.ts",
)
PATTERN_A = (
    "screens/IN/IN202500/extensions/IN202500_QMS.html",
    "screens/IN/IN202500/extensions/IN202500_QMS.ts",
)


class TestPublishedPackageV17(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()

    def test_live_package_has_gi_pattern_b_pattern_a_pages_qm(self) -> None:
        shipped = pack.package_zip(ROOT)
        with zipfile.ZipFile(io.BytesIO(shipped)) as zf:
            shipped_names = set(zf.namelist())
        self.assertIn(
            "_project/GenericInquiryScreen_QM401000.xml",
            shipped_names,
        )
        with client() as session:
            content = session.customization_project_content(PACKAGE_NAME)
        self.assertIsNotNone(content)
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = set(zf.namelist())
            project = ET.fromstring(zf.read("project.xml"))
            qm301 = zf.read("screens/QM/QM301000/QM301000.ts").decode("utf-8")
            qm302 = zf.read("screens/QM/QM302000/QM302000.ts").decode("utf-8")
        for member in PATTERN_B + PATTERN_A:
            self.assertIn(member, names, member)
        pages_qm = [name for name in names if name.startswith("Pages_QM/")]
        self.assertEqual(pages_qm, [])
        for screen in ("QM101000", "QM201000", "QM301000", "QM302000"):
            self.assertIn(f"Pages/QM/{screen}.aspx", names, screen)
            self.assertIn(f"Pages/QM/{screen}.aspx.cs", names, screen)
        self.assertEqual(project.findall("Page"), [])
        per_tenant = {
            (item.get("AppRelativePath"), item.get("ScreenId"))
            for item in project.findall("PerTenantFile")
        }
        self.assertIn((r"screens\QM\QM301000\QM301000.ts", "QM301000"), per_tenant)
        self.assertIn((r"screens\QM\QM302000\QM302000.ts", "QM302000"), per_tenant)
        self.assertIn("EvaluateResults: PXActionState", qm301)
        self.assertIn("ReleaseLotDecision: PXActionState", qm301)
        self.assertIn("hideFilesIndicator: false", qm301)
        self.assertIn("hideNotesIndicator: false", qm301)
        self.assertIn("CloseNCR: PXActionState", qm302)
        self.assertIn("DispositionRTV: PXActionState", qm302)


class TestQualityQueueLiveV16(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not instance().ssh:
            raise unittest.SkipTest("hosted path (blank ACU_SSH) — no sqlcmd")
        ensure_published()

    def test_gidesign_and_drills(self) -> None:
        cid = company_id()
        names = sql_lines(
            f"SELECT Name FROM {DB_NAME}.dbo.GIDesign "
            f"WHERE DesignID = '{GI_DESIGN_ID}' AND CompanyID = 1"
        )
        self.assertTrue(names, "missing GIDesign Quality Queue")
        self.assertTrue(
            any("Quality Queue" in row for row in names),
            names,
        )
        other = sql_lines(
            f"SELECT CompanyID FROM {DB_NAME}.dbo.GIDesign "
            f"WHERE DesignID = '{GI_DESIGN_ID}' AND CompanyID <> 1"
        )
        self.assertEqual(other, [], f"Quality Queue GIDesign not system-only: {other}")
        links = set(
            sql_lines(
                f"SELECT Link FROM {DB_NAME}.dbo.GINavigationScreen "
                f"WHERE DesignID = '{GI_DESIGN_ID}' AND CompanyID IN (1, {cid})"
            )
        )
        self.assertIn("QM301000", links)
        self.assertIn("QM302000", links)
        self.assertNotIn("EvaluateResults", links)
        grouped = sql_lines(
            f"SELECT DataFieldName FROM {DB_NAME}.dbo.GIGroupBy "
            f"WHERE DesignID = '{GI_DESIGN_ID}' AND CompanyID IN (1, {cid})"
        )
        self.assertIn(
            "Order.inspectionOrderNbr",
            grouped,
            f"Quality Queue GIGroupBy missing: {grouped}",
        )
        screens = sql_lines(
            f"SELECT ScreenID FROM {DB_NAME}.dbo.SiteMap "
            f"WHERE ScreenID = N'QM401000' AND CompanyID IN (1, {cid})"
        )
        self.assertTrue(screens, "missing SiteMap QM401000")

    def test_gi_aspx_opens(self) -> None:
        with client() as session:
            response = session._http.get(
                "/GenericInquiry/GenericInquiry.aspx",
                params={"id": GI_DESIGN_ID},
                follow_redirects=True,
            )
        url = str(response.url)
        self.assertNotIn(
            "does+not+exist",
            url,
            f"Quality Queue GI missing: {url}",
        )
        self.assertNotIn("/ui/error", url, f"Quality Queue GI error: {url}")
        self.assertEqual(response.status_code, 200)

    def test_work_row_grain(self) -> None:
        cid = company_id()
        aggs = {}
        for line in sql_lines(
            "SELECT ObjectName, Field, AggregateFunction FROM "
            f"{DB_NAME}.dbo.GIResult "
            f"WHERE DesignID = '{GI_DESIGN_ID}' AND CompanyID IN (1, {cid})"
        ):
            parts = line.split("|")
            obj, field = parts[0], parts[1]
            aggs[f"{obj}.{field}"] = parts[2] if len(parts) > 2 else ""
        for key in (
            "Lot.usrQMSLotStatus",
            "NCR.nCRNbr",
            "NCR.status",
            "Item.inventoryCD",
            "Order.lotSerialNbr",
            "Order.receiptNbr",
            "Vendor.acctCD",
            "Order.planID",
            "Order.status",
        ):
            self.assertEqual(
                aggs.get(key),
                "MAX",
                f"{key} AggregateFunction missing MAX: {aggs}",
            )
        self.assertNotEqual(aggs.get("Order.inspectionOrderNbr"), "MAX")
        work = (
            f"{DB_NAME}.dbo.UsrQMSInspectionOrder o "
            f"LEFT JOIN {DB_NAME}.dbo.INLotSerialStatusByCostCenter lot "
            "ON lot.CompanyID = o.CompanyID "
            "AND lot.InventoryID = o.InventoryID "
            "AND lot.LotSerialNbr = o.LotSerialNbr "
            f"LEFT JOIN {DB_NAME}.dbo.UsrQMSNonConformance n "
            "ON n.CompanyID = o.CompanyID "
            "AND n.InspectionOrderNbr = o.InspectionOrderNbr "
            f"WHERE o.CompanyID IN (1, {cid}) AND ("
            "lot.UsrQMSLotStatus = N'QC Hold' "
            "OR o.Status <> N'C' "
            "OR (n.NCRNbr IS NOT NULL AND n.Status <> N'C'))"
        )
        distinct = sql_lines("SELECT COUNT(DISTINCT o.InspectionOrderNbr) FROM " + work)
        self.assertTrue(distinct)
        if int(distinct[0]) == 0:
            from e2e.test_functional import _order_record, _plan_record, _seed_ready

            with client() as session:
                reason = _seed_ready(session)
                if reason:
                    raise unittest.SkipTest(reason)
                ensure_numbering_and_role(session)
                qms_put(session, "InspectionPlan", _plan_record())
                qms_put(
                    session,
                    "InspectionOrder",
                    _order_record("E2EQQUEUE00001", 0.5, "brown"),
                )
            distinct = sql_lines(
                "SELECT COUNT(DISTINCT o.InspectionOrderNbr) FROM " + work
            )
        self.assertGreater(
            int(distinct[0]),
            0,
            "Quality Queue has no work rows after seeding an open order",
        )
        ncr_rows = sql_lines(
            "SELECT COUNT(*) FROM (SELECT o.InspectionOrderNbr "
            "FROM " + work + " AND n.NCRNbr IS NOT NULL AND n.Status <> N'C' "
            "GROUP BY o.InspectionOrderNbr) q"
        )
        self.assertTrue(ncr_rows)
        if int(ncr_rows[0]) > 0:
            links = set(
                sql_lines(
                    f"SELECT Link FROM {DB_NAME}.dbo.GINavigationScreen "
                    f"WHERE DesignID = '{GI_DESIGN_ID}' "
                    f"AND CompanyID IN (1, {cid})"
                )
            )
            self.assertIn("QM301000", links)
            self.assertIn("QM302000", links)

    def test_roles_in_graph_qm401000(self) -> None:
        cid = company_id()
        present = {
            (role, int(rights))
            for line in sql_lines(
                "SELECT Rolename, Accessrights FROM "
                f"{DB_NAME}.dbo.RolesInGraph WHERE ScreenID = N'QM401000' "
                f"AND CompanyID IN (1, {cid})"
            )
            for role, rights in [line.split("|", 1)]
        }
        missing = [
            role
            for role in QM_RIGHTS_ROLES
            if (role, ACCESSRIGHTS_DELETE) not in present
        ]
        self.assertEqual(missing, [], f"missing QM401000 rights: {missing} ({present})")


class TestStockItemModernUiV17(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not instance().ssh:
            raise unittest.SkipTest("hosted path (blank ACU_SSH) — no ssh")
        ensure_published()

    def test_in202500_qms_published_to_instance(self) -> None:
        tenant = instance().tenant
        base = (
            ACU_INSTANCE_PATH
            + rf"\FrontendSources\screen\src\customizationScreens\{tenant}"
            r"\screens\IN\IN202500\extensions\IN202500_QMS"
        )

        def _read(suffix: str) -> str:
            path = base + suffix
            text = ssh_run(
                "if (Test-Path -LiteralPath '"
                + path.replace("'", "''")
                + "') { Get-Content -LiteralPath '"
                + path.replace("'", "''")
                + "' -Raw } else { Write-Output 'MISSING' }"
            )
            self.assertNotIn("MISSING", text, path)
            return text

        html = _read(".html")
        ts = _read(".ts")
        self.assertIn("UsrQMSInspectionRequired", html)
        self.assertIn("UsrQMSInspectionPlanID", html)
        self.assertIn("UsrMinShelfLifeDays", html)
        self.assertIn("visible.bind", html)
        self.assertNotIn("if.bind", html)
        self.assertIn("export interface InventoryItem_QMS extends InventoryItem", ts)
        self.assertIn("export class InventoryItem_QMS", ts)
        self.assertNotIn("export class InventoryItem {", ts)
        for field in (
            "UsrQMSInspectionRequired",
            "UsrQMSInspectionPlanID",
            "UsrMinShelfLifeDays",
        ):
            self.assertRegex(
                ts,
                rf"@controlConfig\([^)]*\)\s+{field}: PXFieldState",
                field,
            )

    def test_pattern_b_actions_notes_files_on_instance(self) -> None:
        def _read_ts(screen: str) -> str:
            tenant = instance().tenant
            path = (
                ACU_INSTANCE_PATH
                + rf"\FrontendSources\screen\src\customizationScreens\{tenant}"
                rf"\screens\QM\{screen}\{screen}.ts"
            )
            literal = path.replace("'", "''")
            text = ssh_run(
                "if (Test-Path -LiteralPath '"
                + literal
                + "') { Get-Content -LiteralPath '"
                + literal
                + "' -Raw } else { Write-Output 'MISSING' }"
            )
            self.assertNotIn("MISSING", text, path)
            return text

        qm201 = _read_ts("QM201000")
        qm301 = _read_ts("QM301000")
        qm302 = _read_ts("QM302000")
        self.assertIn("EvaluateResults: PXActionState", qm301)
        self.assertIn("ReleaseLotDecision: PXActionState", qm301)
        self.assertIn("hideFilesIndicator: false", qm301)
        self.assertIn("hideNotesIndicator: false", qm301)
        self.assertNotIn("LineNbr: PXFieldState", qm201)
        self.assertNotIn("LineNbr: PXFieldState", qm301)
        self.assertIn("CloseNCR: PXActionState", qm302)
        self.assertIn("DispositionRTV: PXActionState", qm302)

    def test_webpack_emitted_tenant_qm_html(self) -> None:
        tenant = instance().tenant
        missing = []
        for screen in ("QM101000", "QM201000", "QM301000", "QM302000"):
            path = ACU_INSTANCE_PATH + rf"\Scripts\Screens\{tenant}\{screen}.html"
            literal = path.replace("'", "''")
            exists = ssh_run(
                "if (Test-Path -LiteralPath '" + literal + "') { 'YES' } else { 'NO' }"
            ).strip()
            if exists != "YES":
                missing.append(path)
        self.assertEqual(missing, [], f"webpack missed tenant screens: {missing}")
        with client() as session:
            for screen in ("QM101000", "QM201000", "QM301000", "QM302000"):
                response = session._http.get(f"/Scripts/Screens/{tenant}/{screen}.html")
                self.assertEqual(
                    response.status_code,
                    200,
                    f"{screen} compiled html -> {response.status_code}",
                )

    def test_qm_selected_ui_not_classic(self) -> None:
        cid = company_id()
        locked = []
        for line in sql_lines(
            "SELECT ScreenID, CompanyID, SelectedUI FROM "
            f"{DB_NAME}.dbo.SiteMap WHERE ScreenID LIKE N'QM%' "
            f"AND CompanyID IN (1, {cid})"
        ):
            screen, company, ui = line.split("|")[:3]
            if ui != "D":
                locked.append(f"{screen} company {company}={ui}")
        self.assertEqual(locked, [], f"QM screens still Classic-locked: {locked}")


class TestStockItemWebpackExtendsViewV17(unittest.TestCase):
    """V17 / B11: webpack @extendsView so New Record binds Item.UsrQMS* FieldState."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()

    def test_in202500_webpack_extends_view_fieldstate(self) -> None:
        tenant = instance().tenant
        with client() as session:
            compiled = session._http.get(f"/Scripts/Screens/{tenant}/IN202500.html")
            self.assertEqual(
                compiled.status_code,
                200,
                f"IN202500 compiled html -> {compiled.status_code}",
            )
            html = compiled.text
            bundle_name = None
            for token in html.replace("'", '"').split('"'):
                if token.startswith("IN202500.") and token.endswith(".bundle.js"):
                    bundle_name = token
                    break
            self.assertIsNotNone(
                bundle_name, f"IN202500.html missing bundle: {html[:400]}"
            )
            bundle = session._http.get(f"/Scripts/Screens/{tenant}/{bundle_name}")
            screen = session._checked(
                session._http.get(
                    "/Main",
                    params={"ScreenId": "IN202500"},
                    follow_redirects=True,
                )
            )
        self.assertEqual(
            bundle.status_code,
            200,
            f"{bundle_name} -> {bundle.status_code}",
        )
        js = bundle.text
        self.assertIn("extendsView", js)
        self.assertIn("InventoryItem_QMS", js)
        for field in (
            "UsrQMSInspectionRequired",
            "UsrQMSInspectionPlanID",
            "UsrMinShelfLifeDays",
        ):
            self.assertIn(field, js, field)
        self.assertNotIn("cannot be bound to a FieldState", js)
        url = str(screen.url)
        self.assertTrue(
            "ScreenId=IN202500" in url or "ScreenID=IN202500" in url,
            f"IN202500 dropped from url after redirects: {url}",
        )
        self.assertNotRegex(
            url,
            r"\.aspx(\?|$)",
            f"IN202500 opened Classic ASPX: {url}",
        )


if __name__ == "__main__":
    unittest.main()
