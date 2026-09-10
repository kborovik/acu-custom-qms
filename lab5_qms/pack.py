"""Pack Lab5_QMS_Customization.zip (T12 / T14 / V8 / I.pkg).

The zip is an Acumatica CustomizationApi import: project.xml holds
EntityEndpoint, SiteMapNode, Sql, PerTenantFile (Modern UI), and File
items. I.pkg members ride as extra zip entries so the package is
inspectable without unzipping project.xml. Code items use the Source
attribute (CstCodeFile shape, verified vs 26.101.0225 in acumatica-cli
bootstrap).
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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


def ensure_assembly(root: Path | None = None) -> Path:
    """Compile Lab5.QMS.dll when src/Lab5.QMS C# is newer than the assembly."""
    root = ROOT if root is None else Path(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import dll

    return dll.ensure_compiled(root)


def package_zip(root: Path | None = None, *, ensure_dll: bool = False) -> bytes:
    """Build the customization package bytes."""
    root = ROOT if root is None else Path(root)
    if ensure_dll:
        ensure_assembly(root)
    customization = _project_xml(root)
    xml_bytes = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        customization, encoding="utf-8"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.xml", xml_bytes)
        for rel in _pkg_members(root):
            zf.write(root / rel, arcname=rel.as_posix())
        for rel in _frontend_files():
            zf.write(root / rel, arcname=per_tenant_arcname(rel))
        for src in _aspx_sources(root):
            zf.write(root / src, arcname=_aspx_arcname(src))
        dll = _dll_path(root)
        if dll is not None:
            zf.write(dll, arcname="Bin/" + ASSEMBLY_DLL)
    return buf.getvalue()


def write_package(
    dest: Path | None = None,
    root: Path | None = None,
    *,
    ensure_dll: bool = False,
) -> Path:
    """Write Lab5_QMS_Customization.zip and return its path."""
    root = ROOT if root is None else Path(root)
    path = root / PACKAGE_ZIP if dest is None else Path(dest)
    path.write_bytes(package_zip(root, ensure_dll=ensure_dll))
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

    # No <Page>: 26.101 NRE without path; path=~/Pages/QM/*.aspx is not OOTB.
    # Tenant webpack only picks up screens\<Mod>\<ScreenId>\.
    for rel in _frontend_files():
        item = ET.SubElement(customization, "PerTenantFile")
        item.set("AppRelativePath", per_tenant_app_relative(rel))
        item.set("ScreenId", per_tenant_screen_id(rel))
    for src in _aspx_sources(root):
        file_el = ET.SubElement(customization, "File")
        file_el.set("AppRelativePath", _aspx_app_relative(src))

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
        Path("_project") / "GenericInquiryScreen_QM401000.xml",
        Path("Scripts") / "CreateQMSTables.sql",
    ]
    for path in [*members, *_frontend_files()]:
        if not (root / path).is_file():
            raise FileNotFoundError(path)
    return members


def _frontend_qm_files() -> list[Path]:
    files: list[Path] = []
    for screen in PAGES:
        for suffix in (".html", ".ts"):
            files.append(
                Path("FrontendSources")
                / "screen"
                / "src"
                / "screens"
                / "QM"
                / screen
                / f"{screen}{suffix}"
            )
    return files


def _frontend_in202500_qms() -> list[Path]:
    base = (
        Path("FrontendSources")
        / "screen"
        / "src"
        / "screens"
        / "IN"
        / "IN202500"
        / "extensions"
    )
    return [base / "IN202500_QMS.html", base / "IN202500_QMS.ts"]


def _frontend_files() -> list[Path]:
    return [*_frontend_qm_files(), *_frontend_in202500_qms()]


def per_tenant_arcname(rel: Path) -> str:
    """Zip member / CstPerTenantFile path: screens/<Mod>/<ScreenID>/..."""
    parts = rel.parts
    try:
        idx = parts.index("screens")
    except ValueError as exc:
        raise ValueError(f"frontend path missing screens/: {rel}") from exc
    return "/".join(parts[idx:])


def per_tenant_app_relative(rel: Path) -> str:
    return "\\".join(per_tenant_arcname(rel).split("/"))


def per_tenant_screen_id(rel: Path) -> str:
    parts = Path(per_tenant_arcname(rel)).parts
    # screens/<Module>/<ScreenID>/...
    if len(parts) < 3:
        raise ValueError(f"frontend path missing screen id: {rel}")
    return parts[2]


def _aspx_sources(root: Path) -> list[Path]:
    files = [
        Path("Pages_QM") / f"{screen}{suffix}"
        for screen in PAGES
        for suffix in (".aspx", ".aspx.cs")
    ]
    for path in files:
        if not (root / path).is_file():
            raise FileNotFoundError(path)
    return files


def _aspx_arcname(src: Path) -> str:
    return f"Pages/QM/{src.name}"


def _aspx_app_relative(src: Path) -> str:
    return rf"Pages\QM\{src.name}"


def _cs_files(root: Path) -> list[Path]:
    src = root / "src" / "Lab5.QMS"
    files = [
        p for p in src.rglob("*.cs") if "bin" not in p.parts and "obj" not in p.parts
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
    path = write_package(args.output, ensure_dll=True)
    print(path)


if __name__ == "__main__":
    main()
