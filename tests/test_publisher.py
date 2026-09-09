#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T1 / V8: Lab5.QMS publisher identity and I.pkg source layout."""

from __future__ import annotations

import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

USR_QMS_TABLES = (
    "UsrQMSInspectionPlan",
    "UsrQMSInspectionPlanTest",
    "UsrQMSInspectionOrder",
    "UsrQMSInspectionOrderResult",
    "UsrQMSNonConformance",
    "UsrQMSSetup",
)


class TestPublisherV8(unittest.TestCase):
    def test_csproj_assembly_and_namespace(self) -> None:
        csproj = ROOT / "src" / "Lab5.QMS" / "Lab5.QMS.csproj"
        tree = ET.parse(csproj)
        root = tree.getroot()
        # SDK-style csproj has no xmlns; legacy has msbuild xmlns.
        query = ".//{http://schemas.microsoft.com/developer/msbuild/2003}%s"

        def text(tag: str) -> str | None:
            el = root.find(".//" + tag)
            if el is None:
                el = root.find(query % tag)
            return None if el is None else (el.text or "").strip()

        self.assertEqual(text("AssemblyName"), "Lab5.QMS")
        self.assertEqual(text("RootNamespace"), "Lab5.QMS")
        self.assertEqual(text("AcumaticaDir"), r"C:\Acumatica\AcumaticaERP")
        refs = {
            (el.get("Include"), (el.find("HintPath").text or "").strip())
            for el in root.findall("ItemGroup/Reference")
            if el.find("HintPath") is not None
        }
        for name in ("PX.Data", "PX.Objects", "PX.Common", "PX.Common.Std"):
            self.assertIn(
                (name, rf"$(AcumaticaDir)\Bin\{name}.dll"),
                refs,
                name,
            )

    def test_qms_marker_constants(self) -> None:
        src = (ROOT / "src" / "Lab5.QMS" / "QMS.cs").read_text(encoding="utf-8")
        self.assertIn("namespace Lab5.QMS", src)
        self.assertIn('AssemblyFile = "Lab5.QMS.dll"', src)
        self.assertIn('PackageZip = "Lab5_QMS_Customization.zip"', src)
        self.assertIn('EndpointName = "QMS"', src)
        self.assertIn('EndpointVersion = "22.200.001"', src)

    def test_project_metadata(self) -> None:
        path = ROOT / "_project" / "ProjectMetadata.xml"
        root = ET.parse(path).getroot()
        self.assertEqual(root.tag, "project")
        self.assertEqual(root.get("name"), "Lab5.QMS")
        description = root.get("description") or ""
        self.assertIn("22.200.001", description)
        self.assertIn("Lab5.QMS.dll", description)
        self.assertIn("Lab5_QMS_Customization.zip", description)


class TestPkgLayout(unittest.TestCase):
    def test_i_pkg_source_paths(self) -> None:
        self.assertTrue((ROOT / "_project" / "ProjectMetadata.xml").is_file())
        self.assertTrue((ROOT / "Scripts" / "CreateQMSTables.sql").is_file())
        self.assertTrue((ROOT / "src" / "Lab5.QMS" / "Lab5.QMS.csproj").is_file())
        self.assertTrue(
            (
                ROOT
                / "FrontendSources"
                / "screen"
                / "src"
                / "screens"
                / "QM"
                / "QM101000"
                / "QM101000.ts"
            ).is_file()
        )


class TestUsrQmsDdl(unittest.TestCase):
    def test_create_table_for_each_usrqms_entity(self) -> None:
        sql = (ROOT / "Scripts" / "CreateQMSTables.sql").read_text(encoding="utf-8")
        created = set(
            re.findall(
                r"CREATE TABLE \[dbo\]\.\[(UsrQMS[A-Za-z]+)\]",
                sql,
            )
        )
        self.assertEqual(set(USR_QMS_TABLES), created)

    def test_company_id_on_each_table(self) -> None:
        sql = (ROOT / "Scripts" / "CreateQMSTables.sql").read_text(encoding="utf-8")
        for table in USR_QMS_TABLES:
            block = _table_block(sql, table)
            self.assertIn("[CompanyID] [int] NOT NULL", block, table)
            self.assertIn("[tstamp] [timestamp] NOT NULL", block, table)


def _table_block(sql: str, table: str) -> str:
    marker = f"CREATE TABLE [dbo].[{table}]"
    start = sql.index(marker)
    end = sql.find("CREATE TABLE", start + 1)
    return sql[start:] if end < 0 else sql[start:end]


if __name__ == "__main__":
    unittest.main()
