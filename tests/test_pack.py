#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
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

from lab5_qms import pack  # noqa: E402

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
SITEMAP_SCREENS = SCREENS + ("QM401000",)
INVENTORY_WORKSPACE_ID = "6557C1C6-747E-45BB-9072-54F096598D61"
CONFIGURATION_WORKSPACE_ID = "3206E17E-8A34-4E3E-9648-5CEE25DEFDE5"
QMS_WORKSPACE_ID = "C0A1B1E5-0110-4D16-8A00-51E0A1B1E500"
SUBCATEGORY = {
    "QM101000": "8A93637D-B507-4667-A739-ADAF6FB5F7EA",
    "QM201000": "6D40B0B6-18F4-4139-ADAC-8EC8CB2A17EA",
    "QM301000": "38D13A6E-3076-42FB-9FCE-62FA33897DA6",
    "QM302000": "38D13A6E-3076-42FB-9FCE-62FA33897DA6",
    "QM401000": "98E86774-69E3-41EA-B94F-EB2C7A8426D4",
}
QM401000_URL = (
    "~/GenericInquiry/GenericInquiry.aspx?id=9f9483b9-6427-40c6-9c91-96b22c67c28e"
)

CODE_CLASSES = {
    "QMSInspectionPlan": "NewDac",
    "QMSInspectionPlanTest": "NewDac",
    "QMSInspectionOrder": "NewDac",
    "QMSInspectionOrderResult": "NewDac",
    "QMSNonConformance": "NewDac",
    "QMSSetup": "NewDac",
    "InventoryItemExt": "NewDac",
    "INLotSerialStatusExt": "NewDac",
    "INLotSerialStatusByCostCenterExt": "NewDac",
    "QMSInspectionPlanMaint": "NewGraph",
    "QMSInspectionOrderEntry": "NewGraph",
    "QMSNonConformanceEntry": "NewGraph",
    "QMSSetupMaint": "NewGraph",
    "POReceiptEntry_Extension": "ExistingGraph",
    "KitAssemblyEntry_Extension": "ExistingGraph",
    "INIssueEntry_Extension": "ExistingGraph",
    "QMS": "NewFile",
    "QMSAccess": "NewFile",
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

    def test_zip_excludes_role_usersinroles_rolesingraph(self) -> None:
        with _zip() as zf:
            project = zf.read("project.xml").decode("utf-8")
            sql = zf.read("Scripts/CreateQMSTables.sql").decode("utf-8")
            names = " ".join(zf.namelist())
        blob = project + sql + names
        for token in ("RolesInGraph", "UsersInRoles"):
            self.assertNotIn(token, blob, token)
        self.assertNotIn("<Role", project)
        self.assertNotIn("Quality Manager", blob)

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
            tops = {entity.get("name") for entity in endpoint.findall("TopLevelEntity")}
        self.assertEqual(
            tops,
            {
                "InspectionPlan",
                "InspectionOrder",
                "NonConformance",
                "StockItem",
                "QMSSetup",
            },
        )

    def test_code_items_lab5_namespace(self) -> None:
        src = ROOT / "src" / "Lab5.QMS"
        for class_name in CODE_CLASSES:
            hits = list(src.rglob(f"{class_name}.cs"))
            self.assertTrue(hits, class_name)
            source = hits[0].read_text(encoding="utf-8")
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
            self.assertIn(f"Pages/QM/{screen}.aspx", names, screen)
        sitemap = root.find("SiteMapNode")
        self.assertIsNotNone(sitemap)
        site_rows = sitemap.findall(".//SiteMap/row")
        screens = {row.get("ScreenID"): row for row in site_rows if row.get("ScreenID")}
        self.assertNotIn("QM000000", screens)
        self.assertIsNone(sitemap.find(".//MUIWorkspace/row"))
        blob = ET.tostring(sitemap, encoding="unicode")
        self.assertNotIn("Quality Management", blob)
        self.assertNotIn(QMS_WORKSPACE_ID, blob)
        self.assertNotIn(CONFIGURATION_WORKSPACE_ID, blob)
        self.assertNotIn(">Configuration<", blob)
        for screen in SITEMAP_SCREENS:
            self.assertIn(screen, screens, screen)
            row = screens[screen]
            self.assertNotEqual(
                row.get("SelectedUI"),
                "E",
                f"{screen} still SelectedUI=E folder-only",
            )
            mui = row.find("MUIScreen")
            self.assertIsNotNone(mui, f"{screen} missing MUIScreen")
            self.assertEqual(mui.get("WorkspaceID"), INVENTORY_WORKSPACE_ID, screen)
            self.assertEqual(mui.get("SubcategoryID"), SUBCATEGORY[screen], screen)
        for screen in SCREENS:
            self.assertEqual(
                screens[screen].get("Url"),
                f"~/Pages/QM/{screen}.aspx",
                screen,
            )
        self.assertEqual(screens["QM401000"].get("Title"), "Quality Queue")
        self.assertEqual(screens["QM401000"].get("Url"), QM401000_URL)
        pages = {
            item.get("ScreenID"): item
            for item in root.findall("Page")
            if item.get("Type") == "Page"
        }
        for screen in SCREENS:
            self.assertIn(screen, pages, screen)
            self.assertEqual(pages[screen].get("Title"), pack.PAGE_TITLES[screen])
        file_paths = {item.get("AppRelativePath") for item in root.findall("File")}
        for screen in SCREENS:
            for suffix in (".html", ".ts"):
                rel = (
                    rf"FrontendSources\screen\src\screens\QM\{screen}\{screen}{suffix}"
                )
                self.assertIn(rel, file_paths, rel)
                self.assertIn(
                    f"FrontendSources/screen/src/screens/QM/{screen}/{screen}{suffix}",
                    names,
                    screen,
                )


GRAPH_TYPES = {
    "QM101000": "Lab5.QMS.QMSSetupMaint",
    "QM201000": "Lab5.QMS.QMSInspectionPlanMaint",
    "QM301000": "Lab5.QMS.QMSInspectionOrderEntry",
    "QM302000": "Lab5.QMS.QMSNonConformanceEntry",
}


class TestPatternBModernUi(unittest.TestCase):
    def test_screen_class_and_graph_type(self) -> None:
        for screen, graph_type in GRAPH_TYPES.items():
            ts = (
                ROOT
                / "FrontendSources"
                / "screen"
                / "src"
                / "screens"
                / "QM"
                / screen
                / f"{screen}.ts"
            ).read_text(encoding="utf-8")
            self.assertIn(f"export class {screen} extends PXScreen", ts, screen)
            self.assertIn(f'graphType: "{graph_type}"', ts, screen)


class TestPackDllFile(unittest.TestCase):
    def test_zip_includes_bin_dll_when_present(self) -> None:
        dest = ROOT / "src" / "Lab5.QMS" / "bin" / "Release" / pack.ASSEMBLY_DLL
        dest.parent.mkdir(parents=True, exist_ok=True)
        created = not dest.exists()
        previous = dest.read_bytes() if dest.exists() else None
        dest.write_bytes(b"MZ-test-dll")
        try:
            with _zip() as zf:
                names = set(zf.namelist())
                root = _project(zf)
                payload = zf.read("Bin/" + pack.ASSEMBLY_DLL)
            self.assertIn("Bin/" + pack.ASSEMBLY_DLL, names)
            self.assertEqual(payload, b"MZ-test-dll")
            paths = {item.get("AppRelativePath") for item in root.findall("File")}
            self.assertIn(rf"Bin\{pack.ASSEMBLY_DLL}", paths)
        finally:
            if created:
                dest.unlink(missing_ok=True)
            elif previous is not None:
                dest.write_bytes(previous)


if __name__ == "__main__":
    unittest.main()
