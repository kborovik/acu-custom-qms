#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T11 / T25 / I.screen / I.cmd / V14: QMSSetupMaint, QM.10.10.00, numbering QORD / QNCR, post-publish UsrQMSSetup seed."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SETUP_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSSetup.cs"
GRAPH_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "QMSSetupMaint.cs"
RULES_CS = ROOT / "src" / "Lab5.QMS" / "QMSSetupRules.cs"
ORDER_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSInspectionOrder.cs"
ORDER_GRAPH_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "QMSInspectionOrderEntry.cs"
NCR_CS = ROOT / "src" / "Lab5.QMS" / "DAC" / "QMSNonConformance.cs"
NCR_GRAPH_CS = ROOT / "src" / "Lab5.QMS" / "Graph" / "QMSNonConformanceEntry.cs"
ASPX = ROOT / "Pages_QM" / "QM101000.aspx"
SITEMAP = ROOT / "_project" / "SiteMap.xml"
SQL = ROOT / "Scripts" / "CreateQMSTables.sql"

QORD = "QORD"
QNCR = "QNCR"
PREFS_SCREEN = "QM101000"

SETUP_FIELDS = (
    "InspectionOrderNumberingID",
    "NCRNumberingID",
)

WORKSPACE_SCREENS = (
    "QM101000",
    "QM201000",
    "QM301000",
    "QM302000",
)


def _region(src: str, name: str) -> str:
    match = re.search(
        rf"#region {re.escape(name)}\n(.*?)#endregion",
        src,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing #region {name}")
    return match.group(1)


def _table_block(sql: str, table: str) -> str:
    marker = f"CREATE TABLE [dbo].[{table}]"
    start = sql.index(marker)
    end = sql.find("CREATE TABLE", start + 1)
    return sql[start:] if end < 0 else sql[start:end]


class TestQmsSetupNumbering(unittest.TestCase):
    def test_rules_qord_qncr(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(f'InspectionOrderNumberingID = "{QORD}"', src)
        self.assertIn(f'NcrNumberingID = "{QNCR}"', src)
        self.assertIn(f'PrefsScreenID = "{PREFS_SCREEN}"', src)

    def test_setup_dac_defaults_and_selector(self) -> None:
        src = SETUP_CS.read_text(encoding="utf-8")
        self.assertIn("namespace Lab5.QMS", src)
        self.assertIn("class UsrQMSSetup : PXBqlTable, IBqlTable", src)
        self.assertIn("class QMSSetup : UsrQMSSetup", src)
        self.assertIn("[PXTableName]", src)
        self.assertIn("[PXPrimaryGraph(typeof(QMSSetupMaint))]", src)
        order = _region(src, "InspectionOrderNumberingID")
        self.assertIn("[PXDBString(10, IsUnicode = true)]", order)
        self.assertIn("[PXDefault(QMSSetupRules.InspectionOrderNumberingID)]", order)
        self.assertIn("typeof(Numbering.numberingID)", order)
        ncr = _region(src, "NCRNumberingID")
        self.assertIn("[PXDBString(10, IsUnicode = true)]", ncr)
        self.assertIn("[PXDefault(QMSSetupRules.NcrNumberingID)]", ncr)
        self.assertIn("typeof(Numbering.numberingID)", ncr)

    def test_sql_setup_table_and_synonym(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        block = _table_block(sql, "UsrQMSSetup")
        self.assertIn("[UsrQMSSetup_PK]", block)
        self.assertIn("[CompanyID] ASC", block)
        self.assertIn("[InspectionOrderNumberingID] [nvarchar](10) NOT NULL", block)
        self.assertIn("[NCRNumberingID] [nvarchar](10) NOT NULL", block)
        self.assertIn("CREATE SYNONYM [dbo].[QMSSetup] FOR [dbo].[UsrQMSSetup]", sql)


class TestQmsSetupGraphAndScreen(unittest.TestCase):
    def test_graph_setup_view(self) -> None:
        src = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("class QMSSetupMaint : PXGraph<QMSSetupMaint>", src)
        self.assertIn("public PXSave<QMSSetup> Save;", src)
        self.assertIn("public PXCancel<QMSSetup> Cancel;", src)
        self.assertIn("public PXSelect<QMSSetup> Setup;", src)

    def test_screen_qm101000(self) -> None:
        aspx = ASPX.read_text(encoding="utf-8")
        self.assertIn("QM101000", aspx)
        self.assertIn('Title="Quality Preferences"', aspx)
        self.assertIn('TypeName="Lab5.QMS.QMSSetupMaint"', aspx)
        self.assertIn('PrimaryView="Setup"', aspx)
        self.assertIn('DataMember="Setup"', aspx)
        for field in SETUP_FIELDS:
            self.assertIn(f'DataField="{field}"', aspx)

    def test_sitemap_workspace_screens(self) -> None:
        tree = ET.parse(SITEMAP)
        rows = tree.findall(".//row")
        by_screen = {row.get("ScreenID"): row for row in rows if row.get("ScreenID")}
        self.assertIn("QM000000", by_screen)
        self.assertEqual(by_screen["QM000000"].get("Title"), "Quality Management")
        self.assertEqual(by_screen[PREFS_SCREEN].get("Title"), "Quality Preferences")
        self.assertEqual(by_screen[PREFS_SCREEN].get("Url"), "~/Pages/QM/QM101000.aspx")
        for screen_id in WORKSPACE_SCREENS:
            self.assertIn(screen_id, by_screen, screen_id)


class TestAutoNumberWiring(unittest.TestCase):
    def test_order_autonumber_and_setup_view(self) -> None:
        dac = ORDER_CS.read_text(encoding="utf-8")
        region = _region(dac, "InspectionOrderNbr")
        self.assertIn(
            "AutoNumber(typeof(QMSSetup.inspectionOrderNumberingID), typeof(AccessInfo.businessDate))",
            region,
        )
        graph = ORDER_GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("public PXSetup<QMSSetup> QMSSetup;", graph)

    def test_ncr_autonumber_and_setup_view(self) -> None:
        dac = NCR_CS.read_text(encoding="utf-8")
        region = _region(dac, "NCRNbr")
        self.assertIn(
            "AutoNumber(typeof(QMSSetup.nCRNumberingID), typeof(AccessInfo.businessDate))",
            region,
        )
        graph = NCR_GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("public PXSetup<QMSSetup> QMSSetup;", graph)


class TestQmsSetupSeedV14(unittest.TestCase):
    def test_insert_sql_qord_qncr_per_company_when_missing(self) -> None:
        from lab5_qms.publish import QNCR, QORD, qms_setup_insert_sql

        sql = qms_setup_insert_sql()
        self.assertIn("INSERT INTO", sql)
        self.assertIn("UsrQMSSetup", sql)
        self.assertIn("FROM", sql)
        self.assertIn(".dbo.Company", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn(f"N'{QORD}'", sql)
        self.assertIn(f"N'{QNCR}'", sql)
        self.assertIn("InspectionOrderNumberingID", sql)
        self.assertIn("NCRNumberingID", sql)
        self.assertIn("t.CompanyID = c.CompanyID", sql)

    def test_seed_qm_rights_calls_setup_insert(self) -> None:
        src = (ROOT / "lab5_qms" / "publish.py").read_text(encoding="utf-8")
        start = src.index("def seed_qm_rights")
        body = src[start:]
        self.assertIn("_ensure_qms_setup_rows", body)
        self.assertIn("seed UsrQMSSetup", body)
        helper = (ROOT / "e2e" / "helper.py").read_text(encoding="utf-8")
        self.assertIn("_ensure_qms_setup_rows()", helper)
        self.assertNotIn("INSERT INTO", helper[helper.index("def _ensure_setup_row") :])


if __name__ == "__main__":
    unittest.main()
