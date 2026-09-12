#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T12 / T59 / V8 / V27 / I.pkg: pack Lab5_QMS_Customization.zip."""

from __future__ import annotations

import io
import sys
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acuqms import pack  # noqa: E402
from acuqms.paths import FRONTEND_SCREENS_REL  # noqa: E402
from acuqms.publish import package_description  # noqa: E402

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


def _git(
    describe_code: int, describe_out: str, porcelain: str
) -> list[CompletedProcess[str]]:
    return [
        CompletedProcess(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            describe_code,
            stdout=describe_out,
            stderr="",
        ),
        CompletedProcess(
            ["git", "status", "--porcelain"],
            0,
            stdout=porcelain,
            stderr="",
        ),
    ]


class TestPackDescriptionV27(unittest.TestCase):
    """T59 / T60 / V27: pack stamps project.xml; CustomizationApi reads that string."""

    def test_packed_project_xml_matches_package_description(self) -> None:
        zip_bytes = pack.package_zip(ROOT)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            desc = ET.fromstring(zf.read("project.xml")).get("description") or ""
        ver = pack.package_version(ROOT)
        self.assertTrue(desc.startswith(f"Lab5.QMS {ver};"), desc)
        self.assertIn("22.200.001", desc)
        self.assertIn("Lab5.QMS.dll", desc)
        self.assertIn("Lab5_QMS_Customization.zip", desc)
        self.assertIn("[sha256:", desc)
        self.assertEqual(package_description(zip_bytes), desc)
        meta = ET.parse(ROOT / "QMS" / "_project" / "ProjectMetadata.xml").getroot()
        meta_desc = meta.get("description") or ""
        self.assertFalse(meta_desc.startswith("Lab5.QMS "), meta_desc)
        self.assertNotIn("[sha256:", meta_desc)
        src = (ROOT / "acuqms" / "pack.py").read_text(encoding="utf-8")
        self.assertNotIn("api.github.com", src)
        self.assertNotIn("github.com/repos", src)

    def test_e2e_covers_published_description(self) -> None:
        src = (ROOT / "e2e" / "test_package.py").read_text(encoding="utf-8")
        self.assertIn("test_published_description_v27", src)
        self.assertIn("published_description", src)
        self.assertIn("package_version", src)
        self.assertIn('startswith(f"Lab5.QMS {ver}")', src)
        self.assertIn("22.200.001", src)
        self.assertIn("Lab5.QMS.dll", src)
        self.assertIn("[sha256:", src)


class TestPackageVersionDecisionTableV27(unittest.TestCase):
    """T60 / V27: `{ver}` exact-tag+clean / dirty / post-tag / missing-git."""

    def test_package_version_decision_table(self) -> None:
        version = "1.2.3"
        cases = (
            ("exact-tag+clean", _git(0, "v1.2.3\n", ""), "1.2.3"),
            ("dirty", _git(0, "v1.2.3\n", " M acuqms/pack.py\n"), "1.2.3-dev"),
            ("post-tag", _git(128, "", ""), "1.2.3-dev"),
        )
        for name, procs, want in cases:
            with self.subTest(name):
                with (
                    patch("acuqms.pack.pyproject_version", return_value=version),
                    patch("acuqms.pack.subprocess.run", side_effect=procs),
                ):
                    self.assertEqual(pack.package_version(ROOT), want)

    def test_package_version_missing_git(self) -> None:
        with (
            patch("acuqms.pack.pyproject_version", return_value="1.2.3"),
            patch(
                "acuqms.pack.subprocess.run",
                side_effect=FileNotFoundError("git"),
            ),
        ):
            self.assertEqual(pack.package_version(ROOT), "1.2.3-dev")

    def test_packed_description_uses_mocked_package_version(self) -> None:
        with patch("acuqms.pack.package_version", return_value="1.2.3-dev"):
            zip_bytes = pack.package_zip(ROOT)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            desc = ET.fromstring(zf.read("project.xml")).get("description") or ""
        self.assertTrue(desc.startswith("Lab5.QMS 1.2.3-dev;"), desc)
        self.assertIn("22.200.001", desc)
        self.assertIn("Lab5.QMS.dll", desc)
        self.assertIn("[sha256:", desc)
        self.assertEqual(package_description(zip_bytes), desc)


class TestPackZipV8(unittest.TestCase):
    def test_package_zip_name(self) -> None:
        self.assertEqual(pack.PACKAGE_ZIP, "Lab5_QMS_Customization.zip")
        src = (ROOT / "QMS" / "Lab5.QMS" / "QMS.cs").read_text(encoding="utf-8")
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
        self.assertIn("_project/GenericInquiryScreen_QM401000.xml", names)
        self.assertIn("Scripts/CreateQMSTables.sql", names)
        for name in names:
            self.assertFalse(name.startswith("Pages_QM/"), name)
        for screen in SCREENS:
            self.assertIn(f"Pages/QM/{screen}.aspx", names, screen)
            self.assertIn(f"Pages/QM/{screen}.aspx.cs", names, screen)
        meta = ET.parse(ROOT / "QMS" / "_project" / "ProjectMetadata.xml").getroot()
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
        src = ROOT / "QMS" / "Lab5.QMS"
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
        aspx_files = [
            item.get("AppRelativePath")
            for item in root.findall("File")
            if (item.get("AppRelativePath") or "").endswith(".aspx")
            or (item.get("AppRelativePath") or "").endswith(".aspx.cs")
        ]
        for screen in SCREENS:
            self.assertIn(rf"Pages\QM\{screen}.aspx", aspx_files, screen)
            self.assertIn(rf"Pages\QM\{screen}.aspx.cs", aspx_files, screen)
            self.assertIn(f"Pages/QM/{screen}.aspx", names, screen)
            self.assertIn(f"Pages/QM/{screen}.aspx.cs", names, screen)
        for name in names:
            self.assertNotIn("Pages_QM/", name)
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
            self.assertEqual(
                row.get("SelectedUI"),
                "D",
                f"{screen} SelectedUI={row.get('SelectedUI')!r} (want D)",
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
        self.assertEqual(root.findall("Page"), [])
        file_paths = {item.get("AppRelativePath") for item in root.findall("File")}
        per_tenant = {
            (item.get("AppRelativePath"), item.get("ScreenId"))
            for item in root.findall("PerTenantFile")
        }
        for screen in SCREENS:
            for suffix in (".html", ".ts"):
                rel = rf"screens\QM\{screen}\{screen}{suffix}"
                self.assertIn((rel, screen), per_tenant, rel)
                self.assertIn(f"screens/QM/{screen}/{screen}{suffix}", names, screen)
                self.assertNotIn(
                    rf"FrontendSources\screen\src\screens\QM\{screen}\{screen}{suffix}",
                    file_paths,
                    screen,
                )


GRAPH_TYPES = {
    "QM101000": "Lab5.QMS.QMSSetupMaint",
    "QM201000": "Lab5.QMS.QMSInspectionPlanMaint",
    "QM301000": "Lab5.QMS.QMSInspectionOrderEntry",
    "QM302000": "Lab5.QMS.QMSNonConformanceEntry",
}


class TestPerTenantFileHelpers(unittest.TestCase):
    def test_arcname_and_screen_id(self) -> None:
        qm = FRONTEND_SCREENS_REL / "QM" / "QM301000" / "QM301000.ts"
        self.assertEqual(pack.per_tenant_arcname(qm), "screens/QM/QM301000/QM301000.ts")
        self.assertEqual(
            pack.per_tenant_app_relative(qm),
            r"screens\QM\QM301000\QM301000.ts",
        )
        self.assertEqual(pack.per_tenant_screen_id(qm), "QM301000")
        ext = (
            FRONTEND_SCREENS_REL
            / "IN"
            / "IN202500"
            / "extensions"
            / "IN202500_QMS.html"
        )
        self.assertEqual(
            pack.per_tenant_arcname(ext),
            "screens/IN/IN202500/extensions/IN202500_QMS.html",
        )
        self.assertEqual(pack.per_tenant_screen_id(ext), "IN202500")


class TestT48FrontendSourcesLayout(unittest.TestCase):
    """T48 / V17 / I.pkg: Pattern B/A live under development/screens."""

    def test_packer_reads_development_screens_zip_members_unchanged(self) -> None:
        self.assertEqual(
            FRONTEND_SCREENS_REL.as_posix(),
            "QMS/FrontendSources/screen/src/development/screens",
        )
        self.assertFalse((ROOT / "QMS" / "screens").exists())
        rels = pack._frontend_files()
        self.assertGreaterEqual(len(rels), 10)
        for rel in rels:
            self.assertTrue(
                rel.as_posix().startswith(FRONTEND_SCREENS_REL.as_posix() + "/"),
                rel,
            )
            self.assertTrue((ROOT / rel).is_file(), rel)
            arc = pack.per_tenant_arcname(rel)
            self.assertTrue(arc.startswith("screens/"), arc)
            self.assertNotIn("FrontendSources", arc)
            self.assertNotIn("development", arc)
            self.assertFalse(arc.startswith("QMS/"), arc)
        with _zip() as zf:
            names = set(zf.namelist())
        for screen in SCREENS:
            for suffix in (".html", ".ts"):
                self.assertIn(f"screens/QM/{screen}/{screen}{suffix}", names, screen)
        for suffix in (".html", ".ts"):
            self.assertIn(
                f"screens/IN/IN202500/extensions/IN202500_QMS{suffix}",
                names,
            )
        self.assertFalse(any(name.startswith("QMS/screens/") for name in names))
        self.assertFalse(
            any("FrontendSources/screen/src/development" in name for name in names)
        )


class TestPatternBModernUi(unittest.TestCase):
    def test_screen_class_and_graph_type(self) -> None:
        for screen, graph_type in GRAPH_TYPES.items():
            ts = (
                ROOT / FRONTEND_SCREENS_REL / "QM" / screen / f"{screen}.ts"
            ).read_text(encoding="utf-8")
            self.assertIn(f"export class {screen} extends PXScreen", ts, screen)
            self.assertIn(f'graphType: "{graph_type}"', ts, screen)


class TestPatternAStockItem(unittest.TestCase):
    def test_in202500_qms_fields_and_visible_bind(self) -> None:
        base = ROOT / FRONTEND_SCREENS_REL / "IN" / "IN202500" / "extensions"
        html = (base / "IN202500_QMS.html").read_text(encoding="utf-8")
        ts = (base / "IN202500_QMS.ts").read_text(encoding="utf-8")
        self.assertIn("export class IN202500_QMS", ts)
        self.assertIn("export interface InventoryItem_QMS extends InventoryItem", ts)
        self.assertIn("export class InventoryItem_QMS", ts)
        self.assertIn(
            'import { IN202500, InventoryItem } from "src/screens/IN/IN202500/IN202500"',
            ts,
        )
        self.assertNotIn("export class InventoryItem {", ts)
        self.assertNotIn("InventoryItemExtension", ts)
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
        self.assertNotIn("if.bind", html)
        self.assertIn("visible.bind", html)
        for field in (
            "UsrQMSInspectionRequired",
            "UsrQMSInspectionPlanID",
            "UsrMinShelfLifeDays",
        ):
            self.assertIn(f'name="{field}"', html, field)
            self.assertIn(field, ts, field)
        with _zip() as zf:
            root = _project(zf)
            names = set(zf.namelist())
        file_paths = {item.get("AppRelativePath") for item in root.findall("File")}
        per_tenant = {
            (item.get("AppRelativePath"), item.get("ScreenId"))
            for item in root.findall("PerTenantFile")
        }
        for suffix in (".html", ".ts"):
            rel = rf"screens\IN\IN202500\extensions\IN202500_QMS{suffix}"
            self.assertIn((rel, "IN202500"), per_tenant, rel)
            self.assertIn(
                f"screens/IN/IN202500/extensions/IN202500_QMS{suffix}",
                names,
            )
            self.assertNotIn(
                r"FrontendSources\screen\src\screens\IN\IN202500\extensions"
                rf"\IN202500_QMS{suffix}",
                file_paths,
            )


class TestPackDllFile(unittest.TestCase):
    def test_zip_includes_bin_dll_when_present(self) -> None:
        dest = ROOT / "QMS" / "Lab5.QMS" / "bin" / "Release" / pack.ASSEMBLY_DLL
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


class TestE2eInventoryHostedT37(unittest.TestCase):
    """T37 / V16 / V17: live e2e covers Inventory-hosted QM after publish."""

    def test_e2e_covers_inventory_search_package_and_queue(self) -> None:
        hosted = (ROOT / "e2e" / "test_inventory_hosted.py").read_text(encoding="utf-8")
        schema = (ROOT / "e2e" / "test_schema.py").read_text(encoding="utf-8")
        blob = hosted + schema
        self.assertIn("GenericInquiryScreen_QM401000.xml", hosted)
        self.assertIn("EvaluateResults: PXActionState", hosted)
        self.assertIn("ReleaseLotDecision: PXActionState", hosted)
        self.assertIn("CloseNCR: PXActionState", hosted)
        self.assertIn("DispositionRTV: PXActionState", hosted)
        self.assertIn("hideFilesIndicator: false", hosted)
        self.assertIn("hideNotesIndicator: false", hosted)
        self.assertIn("UsrQMSInspectionRequired", hosted)
        self.assertIn("Pages_QM/", hosted)
        self.assertIn("Pages/QM/", hosted)
        self.assertIn('QM_WORKSPACE_TITLE = "Inventory"', schema)
        self.assertIn("Quality Queue", blob)
        self.assertIn("Quality Management", schema)
        self.assertIn("Configuration", schema)
        self.assertIn("QM000000", schema)
        self.assertIn("ScreenId", schema)
        self.assertIn("/Pages/QM/", schema)
        self.assertIn("PerTenantFile", hosted)
        self.assertIn("customizationScreens", hosted)
        self.assertIn("Scripts/Screens", hosted)
        self.assertIn("SelectedUI", hosted)


if __name__ == "__main__":
    unittest.main()
