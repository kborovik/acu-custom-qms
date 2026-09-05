"""Pack Lab5_QMS_Customization.zip (T12 / V8 / I.pkg).

The zip is an Acumatica CustomizationApi import: project.xml holds
EntityEndpoint, SiteMapNode, Sql, Code, and File items. I.pkg members
ride as extra zip entries so the package is inspectable without unzipping
project.xml. Code items use the Source attribute (CstCodeFile shape,
verified vs 26.101.0225 in acumatica-cli bootstrap).
"""

from __future__ import annotations

import argparse
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PACKAGE_ZIP = "Lab5_QMS_Customization.zip"
ASSEMBLY_DLL = "Lab5.QMS.dll"

PAGES = (
    "QM101000",
    "QM201000",
    "QM301000",
    "QM302000",
)

CLASS_RE = re.compile(
    r"public\s+(?:static\s+)?class\s+(\w+)(?:\s*:\s*([^{\n]+))?",
)


def package_zip(root: Path | None = None) -> bytes:
    """Build the customization package bytes."""
    root = ROOT if root is None else Path(root)
    customization = _project_xml(root)
    xml_bytes = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        customization, encoding="utf-8"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.xml", xml_bytes)
        for rel in _pkg_members(root):
            zf.write(root / rel, arcname=rel.as_posix())
        for screen in PAGES:
            for suffix in (".aspx", ".aspx.cs"):
                src = root / "Pages_QM" / f"{screen}{suffix}"
                zf.write(src, arcname=f"Pages/QM/{screen}{suffix}")
        dll = _dll_path(root)
        if dll is not None:
            zf.write(dll, arcname="Bin/" + ASSEMBLY_DLL)
    return buf.getvalue()


def write_package(dest: Path | None = None, root: Path | None = None) -> Path:
    """Write Lab5_QMS_Customization.zip and return its path."""
    root = ROOT if root is None else Path(root)
    path = root / PACKAGE_ZIP if dest is None else Path(dest)
    path.write_bytes(package_zip(root))
    return path


def _project_xml(root: Path) -> ET.Element:
    meta = ET.parse(root / "_project" / "ProjectMetadata.xml").getroot()
    customization = ET.Element("Customization")
    customization.set("level", meta.get("level") or "0")
    customization.set("description", meta.get("description") or "")
    customization.set("product-version", "22.200.001")

    endpoint_doc = ET.parse(root / "_project" / "QMS.xml")
    customization.append(endpoint_doc.getroot())

    sitemap_doc = ET.parse(root / "_project" / "SiteMap.xml")
    customization.append(sitemap_doc.getroot())

    sql_el = ET.SubElement(customization, "Sql")
    sql_el.set("TableName", "CreateQMSTables")
    sql_el.set(
        "CustomScript",
        (root / "Scripts" / "CreateQMSTables.sql").read_text(encoding="utf-8"),
    )

    # C# CstCodeFile <Graph Source FileType=NewDac|NewGraph|NewFile> import
    # succeeds but publishBegin CstCodeFile.Upgrade KeyNotFoundException on
    # 26.101.0225 (includedAspxFiles). Training packages ship Bin\*.dll.
    # Keep DAC/graph source in src/; pack as File once a DLL is produced.
    for screen in PAGES:
        for suffix in (".aspx", ".aspx.cs"):
            file_el = ET.SubElement(customization, "File")
            file_el.set("AppRelativePath", rf"Pages\QM\{screen}{suffix}")

    dll = _dll_path(root)
    if dll is not None:
        file_el = ET.SubElement(customization, "File")
        file_el.set("AppRelativePath", rf"Bin\{ASSEMBLY_DLL}")

    return customization


def _pkg_members(root: Path) -> list[Path]:
    members = [
        Path("_project") / "ProjectMetadata.xml",
        Path("_project") / "QMS.xml",
        Path("_project") / "SiteMap.xml",
        Path("Scripts") / "CreateQMSTables.sql",
    ]
    for screen in PAGES:
        members.append(Path("Pages_QM") / f"{screen}.aspx")
        members.append(Path("Pages_QM") / f"{screen}.aspx.cs")
    for path in members:
        if not (root / path).is_file():
            raise FileNotFoundError(path)
    return members


def _cs_files(root: Path) -> list[Path]:
    src = root / "src" / "Lab5.QMS"
    files = [
        p
        for p in src.rglob("*.cs")
        if "bin" not in p.parts and "obj" not in p.parts
    ]
    files.sort()
    if not files:
        raise FileNotFoundError("src/Lab5.QMS/*.cs")
    return files


def _classify_cs(source: str, fallback: str) -> tuple[str, str, str]:
    """Return (xml_tag, class_name, FileType).

    CstCodeFile.Tag is always Graph. FileType is NewDac / NewGraph /
    ExistingGraph / NewFile (verified vs PX.Web.Customization.dll on
    26.101.0225). Wrong FileType → KeyNotFoundException in Upgrade().
    """
    match = CLASS_RE.search(source)
    if match is None:
        return "Graph", fallback, "NewFile"
    name = match.group(1)
    bases = match.group(2) or ""
    if "PXCacheExtension" in bases or "PXBqlTable" in bases or "IBqlTable" in bases:
        return "Graph", name, "NewDac"
    if "PXGraphExtension" in bases:
        return "Graph", name, "ExistingGraph"
    if "PXGraph" in bases:
        return "Graph", name, "NewGraph"
    return "Graph", name, "NewFile"


def _dll_path(root: Path) -> Path | None:
    hits = sorted(
        p
        for p in (root / "src" / "Lab5.QMS").glob("bin/**/" + ASSEMBLY_DLL)
        if p.is_file()
    )
    return hits[0] if hits else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack Lab5_QMS_Customization.zip")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output zip path (default: ./Lab5_QMS_Customization.zip)",
    )
    args = parser.parse_args()
    path = write_package(args.output)
    print(path)


if __name__ == "__main__":
    main()
