"""T12 / V8 / I.pkg: pack Lab5_QMS_Customization.zip."""

from __future__ import annotations

import io
import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pack  # noqa: E402

ENDPOINT_NS = "{http://www.acumatica.com/entity/maintenance/5.31}"

USR_QMS_TABLES = (
    "UsrQMSInspectionPlan",
    "UsrQMSInspectionPlanTest",
    "UsrQMSInspectionOrder",
    "UsrQMSInspectionOrderResult",
    "UsrQMSNonConformance",
    "UsrQMSSetup",
)

SCREENS = (
    "QM101000",
    "QM201000",
    "QM301000",
    "QM302000",
)

CODE_CLASSES = {
    "QMSInspectionPlan": "DAC",
    "QMSInspectionPlanTest": "DAC",
    "QMSInspectionOrder": "DAC",
    "QMSInspectionOrderResult": "DAC",
    "QMSNonConformance": "DAC",
    "QMSSetup": "DAC",
    "InventoryItemExt": "DAC",
    "QMSInspectionPlanMaint": "Graph",
    "QMSInspectionOrderEntry": "Graph",
    "QMSNonConformanceEntry": "Graph",
    "QMSSetupMaint": "Graph",
    "POReceiptEntry_Extension": "Graph",
    "QMS": "Code",
}


def _zip() -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(pack.package_zip(ROOT)))


def _project(zf: zipfile.ZipFile) -> ET.Element:
    return ET.fromstring(zf.read("project.xml"))


class TestPackZipV8(unittest.TestCase):
    def test_package_zip_name(self) -> None:
        self.assertEqual(pack.PACKAGE_ZIP, "Lab5_QMS_Customization.zip")
        src = (ROOT / "src" / "Lab5.QMS" / "QMS.cs").read_text(encoding="utf-8")
        self.assertIn('PackageZip = "Lab5_QMS_Customization.zip"', src)
        self.assertIn('AssemblyFile = "Lab5.QMS.dll"', src)
        self.assertIn("namespace Lab5.QMS", src)

    def test_customization_root_publisher_identity(self) -> None:
        with _zip() as zf:
            root = _project(zf)
        self.assertEqual(root.tag, "Customization")
        self.assertEqual(root.get("level"), "0")
        self.assertEqual(root.get("product-version"), "22.200.001")
        description = root.get("description") or ""
        self.assertIn("22.200.001", description)
        self.assertIn("Lab5.QMS.dll", description)
        self.assertIn("Lab5_QMS_Customization.zip", description)


class TestPackIPkg(unittest.TestCase):
    def test_i_pkg_zip_members(self) -> None:
        with _zip() as zf:
            names = set(zf.namelist())
        self.assertIn("project.xml", names)
        self.assertIn("_project/ProjectMetadata.xml", names)
        self.assertIn("Scripts/CreateQMSTables.sql", names)
        for screen in SCREENS:
            self.assertIn(f"Pages_QM/{screen}.aspx", names, screen)
        meta = ET.parse(ROOT / "_project" / "ProjectMetadata.xml").getroot()
        self.assertEqual(meta.get("name"), "Lab5.QMS")
        self.assertIn("22.200.001", meta.get("description") or "")

    def test_packed_sql_creates_usrqms_tables(self) -> None:
        with _zip() as zf:
            sql = zf.read("Scripts/CreateQMSTables.sql").decode("utf-8")
            root = _project(zf)
        script = root.find("Sql")
        self.assertIsNotNone(script)
        self.assertEqual(script.get("TableName"), "CreateQMSTables")
        custom = script.get("CustomScript") or ""
        self.assertEqual(custom, sql)
        for table in USR_QMS_TABLES:
            self.assertIn(f"CREATE TABLE [dbo].[{table}]", sql, table)


class TestProjectXmlPackedItems(unittest.TestCase):
    def test_entity_endpoint_from_qms_xml(self) -> None:
        with _zip() as zf:
            root = _project(zf)
        endpoint_item = root.find("EntityEndpoint")
        self.assertIsNotNone(endpoint_item)
        endpoint = endpoint_item.find(f"{ENDPOINT_NS}Endpoint")
        if endpoint is None:
            endpoint = endpoint_item.find("Endpoint")
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.get("name"), "QMS")
        self.assertEqual(endpoint.get("version"), "22.200.001")
        tops = {
            entity.get("name")
            for entity in endpoint.findall(f"{ENDPOINT_NS}TopLevelEntity")
        }
        if not tops:
            tops = {
                entity.get("name") for entity in endpoint.findall("TopLevelEntity")
            }
        self.assertEqual(tops, {"InspectionPlan", "InspectionOrder", "NonConformance"})

    def test_code_items_lab5_namespace(self) -> None:
        with _zip() as zf:
            root = _project(zf)
        by_class: dict[str, ET.Element] = {}
        for tag in ("DAC", "Graph", "Code"):
            for item in root.findall(tag):
                by_class[item.get("ClassName")] = item
        for class_name, tag in CODE_CLASSES.items():
            self.assertIn(class_name, by_class, class_name)
            item = by_class[class_name]
            self.assertEqual(item.tag, tag, class_name)
            self.assertEqual(item.get("FileType"), "NewFile", class_name)
            source = item.get("Source") or ""
            self.assertIn("namespace Lab5.QMS", source, class_name)
            self.assertIn(f"class {class_name}", source, class_name)

    def test_pages_and_sitemap(self) -> None:
        with _zip() as zf:
            root = _project(zf)
            names = set(zf.namelist())
        paths = {
            item.get("AppRelativePath")
            for item in root.findall("File")
            if (item.get("AppRelativePath") or "").endswith(".aspx")
        }
        for screen in SCREENS:
            self.assertIn(rf"Pages\QM\{screen}.aspx", paths, screen)
            self.assertIn(f"Pages_QM/{screen}.aspx", names, screen)
        sitemap = root.find("SiteMap")
        self.assertIsNotNone(sitemap)
        screens = {
            row.get("ScreenID")
            for row in sitemap.findall(".//row")
            if row.get("ScreenID")
        }
        self.assertIn("QM000000", screens)
        for screen in SCREENS:
            self.assertIn(screen, screens, screen)


if __name__ == "__main__":
    unittest.main()
