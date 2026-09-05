#!/usr/bin/env -S uv run
"""Compile Lab5.QMS.dll on the ERP VM (SSH) and copy it back (V8 / I.pkg).

The live 26.101.0225 box has no Visual Studio MSBuild and no dotnet SDK.
It does ship Roslyn csc next to the site Bin (`Bin\\roslyn\\csc.exe`). This
script zips `src/Lab5.QMS` sources, compiles there against PX.Data /
PX.Objects / PX.Common / PX.Common.Std, and writes
`src/Lab5.QMS/bin/Release/Lab5.QMS.dll` for `gmake pack`.

Hosted path (blank ACU_SSH) cannot compile — that is a hard error.
Never prints ACU_PASSWORD.
"""

from __future__ import annotations

import io
import subprocess
import zipfile
from pathlib import Path

from acumatica_cli.config import ACU_INSTANCE_PATH, load_instance
from acumatica_cli.tenant import TenantManager

import pack

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "Lab5.QMS"
REMOTE_ZIP = "lab5-qms-src.zip"
REMOTE_DIR = "lab5-qms-build"
PX_ASSEMBLIES = ("PX.Data", "PX.Objects", "PX.Common", "PX.Common.Std")
FRAMEWORK_DIR = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319"
FRAMEWORK_ASSEMBLIES = (
    "System",
    "System.Core",
    "System.Xml",
    "System.Data",
    "System.Configuration",
    "System.Web",
    "System.Drawing",
    "System.Runtime.Serialization",
    "System.Net.Http",
    "System.Transactions",
)


def source_files(root: Path | None = None) -> list[Path]:
    """Project .cs files, excluding bin/ and obj/."""
    src = SRC if root is None else Path(root) / "src" / "Lab5.QMS"
    files = [
        path
        for path in src.rglob("*.cs")
        if "bin" not in path.parts and "obj" not in path.parts
    ]
    files.sort()
    if not files:
        raise FileNotFoundError("src/Lab5.QMS/*.cs")
    return files


def build_ps1(*, site: str = ACU_INSTANCE_PATH) -> str:
    """PowerShell that runs site Roslyn csc against the extracted sources."""
    px_list = ", ".join(f"'{name}'" for name in PX_ASSEMBLIES)
    fw_list = ", ".join(f"'{name}'" for name in FRAMEWORK_ASSEMBLIES)
    return f"""$ErrorActionPreference = 'Stop'
$Site = '{site}'
$Csc = Join-Path $Site 'Bin\\roslyn\\csc.exe'
if (-not (Test-Path -LiteralPath $Csc)) {{
    throw "Roslyn csc missing: $Csc"
}}
$Fw = '{FRAMEWORK_DIR}'
$OutDir = Join-Path $PSScriptRoot 'bin\\Release'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Out = Join-Path $OutDir '{pack.ASSEMBLY_DLL}'
$px = @({px_list}) | ForEach-Object {{
    $p = Join-Path $Site "Bin\\$_.dll"
    if (-not (Test-Path -LiteralPath $p)) {{ throw "missing $p" }}
    "/reference:$p"
}}
$sys = @({fw_list}) | ForEach-Object {{
    $p = Join-Path $Fw "$_.dll"
    if (Test-Path -LiteralPath $p) {{ "/reference:$p" }}
}}
Set-Location -LiteralPath $PSScriptRoot
& $Csc /nologo /noconfig /target:library /optimize+ /langversion:latest /out:$Out @px @sys /recurse:*.cs
if ($LASTEXITCODE -ne 0) {{
    throw "csc failed ($LASTEXITCODE)"
}}
if (-not (Test-Path -LiteralPath $Out)) {{
    throw "csc produced no $Out"
}}
Write-Output $Out
"""


def source_zip(root: Path | None = None) -> bytes:
    """Zip compile inputs: .cs sources, csproj, and build.ps1."""
    src = SRC if root is None else Path(root) / "src" / "Lab5.QMS"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source_files(root):
            zf.write(path, arcname=path.relative_to(src).as_posix())
        csproj = src / "Lab5.QMS.csproj"
        zf.write(csproj, arcname=csproj.name)
        zf.writestr("build.ps1", build_ps1())
    return buf.getvalue()


def local_dll_path(root: Path | None = None) -> Path:
    base = ROOT if root is None else Path(root)
    return base / "src" / "Lab5.QMS" / "bin" / "Release" / pack.ASSEMBLY_DLL


def _scp(src: str, dst: str) -> None:
    result = subprocess.run(
        ["scp", "-o", "BatchMode=yes", src, dst],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"scp failed ({result.returncode}):\n{result.stdout}\n{result.stderr}"
        )


def compile_on_vm(root: Path | None = None) -> Path:
    """SSH compile on the .env instance; write bin/Release/Lab5.QMS.dll."""
    inst = load_instance()
    if not inst.ssh:
        raise SystemExit(
            "ACU_SSH empty — hosted path cannot compile Lab5.QMS.dll"
        )
    dest = local_dll_path(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    mgr = TenantManager(inst)
    temp = mgr._ssh("$env:TEMP").strip().splitlines()[-1].strip()
    if not temp:
        raise RuntimeError("remote $env:TEMP was empty")
    posix_temp = temp.replace("\\", "/")
    remote_zip = f"{posix_temp}/{REMOTE_ZIP}"
    remote_work = f"{temp}\\{REMOTE_DIR}"
    local_zip = dest.parent / REMOTE_ZIP
    local_zip.write_bytes(source_zip(root))
    try:
        _scp(str(local_zip), f"{inst.ssh}:{remote_zip}")
        mgr._ssh(
            "$ErrorActionPreference = 'Stop'; "
            f"$zip = '{temp}\\{REMOTE_ZIP}'; "
            f"$work = '{remote_work}'; "
            "if (Test-Path -LiteralPath $work) { "
            "Remove-Item -LiteralPath $work -Recurse -Force }; "
            "New-Item -ItemType Directory -Path $work | Out-Null; "
            "Expand-Archive -LiteralPath $zip -DestinationPath $work -Force; "
            "Set-Location -LiteralPath $work; "
            "& .\\build.ps1"
        )
        remote_dll = f"{posix_temp}/{REMOTE_DIR}/bin/Release/{pack.ASSEMBLY_DLL}"
        _scp(f"{inst.ssh}:{remote_dll}", str(dest))
    finally:
        local_zip.unlink(missing_ok=True)
    if not dest.is_file():
        raise RuntimeError(f"DLL was not copied to {dest}")
    return dest


def main() -> None:
    path = compile_on_vm()
    print(path)


if __name__ == "__main__":
    main()
