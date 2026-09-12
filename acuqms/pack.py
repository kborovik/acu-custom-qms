"""Pack Lab5_QMS_Customization.zip (T12 / T14 / T59 / V8 / V27 / I.pkg).

The zip is an Acumatica CustomizationApi import: project.xml holds
EntityEndpoint, SiteMapNode, Sql, PerTenantFile (Modern UI), and File
items. I.pkg members ride as extra zip entries so the package is
inspectable without unzipping project.xml. Code items use the Source
attribute (CstCodeFile shape, verified vs 26.101.0225 in acumatica-cli
bootstrap).

Pack stamps zip project.xml Description `Lab5.QMS {ver}; … [sha256:]`
(V27). Committed `_project/ProjectMetadata.xml` stays a template.
Pack does not call the GitHub API.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import subprocess
import tomllib
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from acuqms.paths import FRONTEND_SCREENS_REL, cs_root, customization_root, sql_file

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
PYPROJECT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
DESCRIPTION_BODY = (
    "QMS customization 22.200.001; assembly Lab5.QMS.dll; "
    "zip Lab5_QMS_Customization.zip"
)
GIT_TIMEOUT = 10.0


def zip_digest(zip_bytes: bytes) -> str:
    """SHA-256 of every zip member (name + bytes), sorted.

    Publish skip used to hash only project.xml + Bin/Lab5.QMS.dll, so an
    ASPX/SQL-only change looked identical and the tenant kept old pages.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        digest = hashlib.sha256()
        for name in sorted(zf.namelist()):
            if name.endswith("/"):
                continue
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(zf.read(name))
        return digest.hexdigest()


def pyproject_version(root: Path | None = None) -> str:
    """X.Y.Z from pyproject.toml (not the live `{ver}` stamp)."""
    root = ROOT if root is None else Path(root)
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(data["project"]["version"])
    if not PYPROJECT_VERSION_RE.fullmatch(version):
        raise ValueError(f"pyproject version must be X.Y.Z (got {version!r})")
    return version


def package_version(root: Path | None = None) -> str:
    """Live `{ver}` for V27: X.Y.Z on exact tag `vX.Y.Z` + clean tree, else `-dev`.

    Missing git, a dirty tree, or HEAD not exactly `v{pyproject}` → `{X.Y.Z}-dev`.
    Does not call the GitHub API.
    """
    root = ROOT if root is None else Path(root)
    version = pyproject_version(root)
    if _release_head(root, version):
        return version
    return f"{version}-dev"


def format_package_description(
    version: str, digest: str, *, body: str | None = None
) -> str:
    """`Lab5.QMS {ver}; QMS customization 22.200.001; … [sha256:{digest}]`."""
    suffix = body if body else DESCRIPTION_BODY
    return f"Lab5.QMS {version}; {suffix} [sha256:{digest}]"


def _release_head(root: Path, version: str) -> bool:
    try:
        describe = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except OSError, subprocess.TimeoutExpired:
        return False
    if describe.returncode != 0 or status.returncode != 0:
        return False
    if describe.stdout.strip() != f"v{version}":
        return False
    return not status.stdout.strip()


def ensure_assembly(root: Path | None = None) -> Path:
    """Compile Lab5.QMS.dll when QMS/Lab5.QMS C# is newer than the assembly."""
    from acuqms.dll import ensure_compiled

    root = ROOT if root is None else Path(root)
    return ensure_compiled(root)


def package_zip(root: Path | None = None, *, ensure_dll: bool = False) -> bytes:
    """Build the customization package bytes.

    Two-pass: hash members with the ProjectMetadata template Description,
    then stamp zip `project.xml` with `Lab5.QMS {ver}; … [sha256:]` (V27).
    The digest excludes the live stamp so `{ver}` is not inside its own hash.
    """
    root = ROOT if root is None else Path(root)
    if ensure_dll:
        ensure_assembly(root)
    customization = _project_xml(root)
    members = _zip_member_bytes(root)
    template = customization.get("description") or DESCRIPTION_BODY
    unstamped = _assemble_zip(_project_xml_bytes(customization, template), members)
    stamped = format_package_description(
        package_version(root), zip_digest(unstamped), body=template
    )
    return _assemble_zip(_project_xml_bytes(customization, stamped), members)


def _project_xml_bytes(customization: ET.Element, description: str) -> bytes:
    customization.set("description", description)
    return b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        customization, encoding="utf-8"
    )


def _zip_member_bytes(root: Path) -> list[tuple[str, bytes]]:
    members: list[tuple[str, bytes]] = []
    for rel, arcname in _pkg_members(root):
        members.append((arcname, (root / rel).read_bytes()))
    for rel in _frontend_files():
        members.append((per_tenant_arcname(rel), (root / rel).read_bytes()))
    for src in _aspx_sources(root):
        members.append((_aspx_arcname(src), (root / src).read_bytes()))
    dll = _dll_path(root)
    if dll is not None:
        members.append(("Bin/" + ASSEMBLY_DLL, dll.read_bytes()))
    return members


def _assemble_zip(project_xml: bytes, members: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.xml", project_xml)
        for arcname, payload in members:
            zf.writestr(arcname, payload)
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
    proj = customization_root(root) / "_project"
    meta = ET.parse(proj / "ProjectMetadata.xml").getroot()
    customization = ET.Element("Customization")
    customization.set("level", meta.get("level") or "0")
    customization.set("description", meta.get("description") or "")
    customization.set("product-version", "22.200.001")

    endpoint_doc = ET.parse(proj / "QMS.xml")
    customization.append(endpoint_doc.getroot())

    sitemap_doc = ET.parse(proj / "SiteMap.xml")
    customization.append(sitemap_doc.getroot())

    sql_el = ET.SubElement(customization, "Sql")
    sql_el.set("TableName", "CreateQMSTables")
    sql_el.set(
        "CustomScript",
        sql_file(root).read_text(encoding="utf-8"),
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


def _pkg_members(root: Path) -> list[tuple[Path, str]]:
    """(path relative to repo root, zip arcname). Zip names stay I.pkg."""
    qms = Path("QMS")
    members = [
        (qms / "_project" / "ProjectMetadata.xml", "_project/ProjectMetadata.xml"),
        (qms / "_project" / "QMS.xml", "_project/QMS.xml"),
        (qms / "_project" / "SiteMap.xml", "_project/SiteMap.xml"),
        (
            qms / "_project" / "GenericInquiryScreen_QM401000.xml",
            "_project/GenericInquiryScreen_QM401000.xml",
        ),
        (qms / "SQL" / "CreateQMSTables.sql", "Scripts/CreateQMSTables.sql"),
    ]
    for rel, _arc in members:
        if not (root / rel).is_file():
            raise FileNotFoundError(rel)
    for path in _frontend_files():
        if not (root / path).is_file():
            raise FileNotFoundError(path)
    return members


def _frontend_qm_files() -> list[Path]:
    files: list[Path] = []
    for screen in PAGES:
        for suffix in (".html", ".ts"):
            files.append(FRONTEND_SCREENS_REL / "QM" / screen / f"{screen}{suffix}")
    return files


def _frontend_in202500_qms() -> list[Path]:
    base = FRONTEND_SCREENS_REL / "IN" / "IN202500" / "extensions"
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
        Path("QMS") / "Pages" / "QM" / f"{screen}{suffix}"
        for screen in PAGES
        for suffix in (".aspx", ".aspx.cs")
    ]
    for path in files:
        if not (root / path).is_file():
            raise FileNotFoundError(path)
    return files


def _aspx_arcname(src: Path) -> str:
    parts = src.parts
    idx = parts.index("Pages")
    return "/".join(parts[idx:])


def _aspx_app_relative(src: Path) -> str:
    return "\\".join(_aspx_arcname(src).split("/"))


def _cs_files(root: Path) -> list[Path]:
    src = cs_root(root)
    files = [
        p for p in src.rglob("*.cs") if "bin" not in p.parts and "obj" not in p.parts
    ]
    files.sort()
    if not files:
        raise FileNotFoundError("QMS/Lab5.QMS/*.cs")
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
        p for p in cs_root(root).glob("bin/**/" + ASSEMBLY_DLL) if p.is_file()
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
