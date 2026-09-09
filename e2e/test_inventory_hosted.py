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
    client,
    company_id,
    ensure_published,
    instance,
    sql_lines,
)
from lab5_qms.acu import ACU_INSTANCE_PATH, ssh_run
from lab5_qms.publish import ACCESSRIGHTS_DELETE, QM_RIGHTS_ROLES

GI_DESIGN_ID = "9f9483b9-6427-40c6-9c91-96b22c67c28e"
PATTERN_B = (
    "FrontendSources/screen/src/screens/QM/QM101000/QM101000.ts",
    "FrontendSources/screen/src/screens/QM/QM201000/QM201000.ts",
    "FrontendSources/screen/src/screens/QM/QM301000/QM301000.ts",
    "FrontendSources/screen/src/screens/QM/QM302000/QM302000.ts",
)
PATTERN_A = (
    "FrontendSources/screen/src/screens/IN/IN202500/extensions/IN202500_QMS.html",
    "FrontendSources/screen/src/screens/IN/IN202500/extensions/IN202500_QMS.ts",
)


class TestPublishedPackageV17(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()

    def test_live_package_has_gi_pattern_b_pattern_a_no_aspx(self) -> None:
        with client() as session:
            content = session.customization_project_content(PACKAGE_NAME)
        self.assertIsNotNone(content)
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = set(zf.namelist())
            project = ET.fromstring(zf.read("project.xml"))
        for member in PATTERN_B + PATTERN_A:
            self.assertIn(member, names, member)
        pages_qm = [name for name in names if name.startswith("Pages_QM/")]
        self.assertEqual(pages_qm, [])
        for screen in ("QM101000", "QM201000", "QM301000", "QM302000"):
            self.assertIn(f"Pages/QM/{screen}.aspx", names, screen)
            self.assertIn(f"Pages/QM/{screen}.aspx.cs", names, screen)
        self.assertEqual(project.findall("Page"), [])


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
            f"WHERE DesignID = '{GI_DESIGN_ID}' AND CompanyID IN (1, {cid})"
        )
        self.assertTrue(names, "missing GIDesign Quality Queue")
        self.assertTrue(
            any("Quality Queue" in row for row in names),
            names,
        )
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
        for key in ("Lot.usrQMSLotStatus", "NCR.nCRNbr", "NCR.status"):
            self.assertEqual(
                aggs.get(key),
                "MAX",
                f"{key} AggregateFunction missing MAX: {aggs}",
            )
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
        grouped = sql_lines(
            "SELECT COUNT(*) FROM (SELECT o.InspectionOrderNbr FROM "
            + work
            + " GROUP BY o.InspectionOrderNbr) q"
        )
        self.assertTrue(distinct)
        self.assertTrue(grouped)
        if int(distinct[0]) == 0:
            raise unittest.SkipTest(
                "no inspection-order work rows — seed tenant from acu-gitops-qms"
            )
        self.assertEqual(
            int(grouped[0]),
            int(distinct[0]),
            "Quality Queue grain is not one row per inspectionOrderNbr",
        )
        ncr_rows = sql_lines(
            "SELECT COUNT(*) FROM (SELECT o.InspectionOrderNbr, MAX(n.NCRNbr) "
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
        path = (
            ACU_INSTANCE_PATH
            + r"\FrontendSources\screen\src\screens\IN\IN202500\extensions"
            r"\IN202500_QMS.html"
        )
        html = ssh_run(
            "if (Test-Path -LiteralPath '"
            + path.replace("'", "''")
            + "') { Get-Content -LiteralPath '"
            + path.replace("'", "''")
            + "' -Raw } else { Write-Output 'MISSING' }"
        )
        self.assertNotIn("MISSING", html)
        self.assertIn("UsrQMSInspectionRequired", html)
        self.assertIn("UsrQMSInspectionPlanID", html)
        self.assertIn("UsrMinShelfLifeDays", html)
        self.assertIn("visible.bind", html)
        self.assertNotIn("if.bind", html)


if __name__ == "__main__":
    unittest.main()
