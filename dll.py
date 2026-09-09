#!/usr/bin/env -S uv run
"""Compile Lab5.QMS.dll on the ERP VM (SSH) and copy it back (V8 / I.pkg).

The live 26.101.0225 box has no Visual Studio MSBuild and no dotnet SDK.
It does ship Roslyn csc next to the site Bin (`Bin\\roslyn\\csc.exe`). This
script zips `src/Lab5.QMS` sources, compiles there against PX.Data /
PX.Objects / PX.Common / PX.Common.Std, and writes
`src/Lab5.QMS/bin/Release/Lab5.QMS.dll`.

Pack, publish, deploy, live e2e, and release call `ensure_compiled` so a
C# change under `src/Lab5.QMS` rebuilds the assembly. A matching
`Lab5.QMS.dll.inputs` fingerprint skips SSH.

Hosted path (blank ACU_SSH) cannot compile — that is a hard error.
Never prints ACU_PASSWORD.
"""

from __future__ import annotations

import io
import subprocess
import zipfile
from pathlib import Path

from lab5_qms import pack
from lab5_qms.acu import ACU_INSTANCE_PATH, load_instance, ssh_run

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / "Lab5.QMS"
REMOTE_ZIP = "lab5-qms-src.zip"
REMOTE_DIR = "lab5-qms-build"
PX_ASSEMBLIES = (
    "PX.Data",
    "PX.Objects",
    "PX.Common",
    "PX.Common.Std",
    "PX.DbServices",
)
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


def compile_inputs(root: Path | None = None) -> list[Path]:
    """Sources that change the assembly: project .cs, csproj, and this compiler."""
    base = ROOT if root is None else Path(root)
    files = list(source_files(root))
    files.append(base / "src" / "Lab5.QMS" / "Lab5.QMS.csproj")
    files.append(base / "dll.py")
    files.sort()
    return files


def inputs_stamp(dest: Path) -> Path:
    return Path(str(dest) + ".inputs")


def inputs_fingerprint(root: Path | None = None) -> str:
    base = ROOT if root is None else Path(root)
    lines: list[str] = []
    for path in compile_inputs(root):
        st = path.stat()
        rel = path.relative_to(base).as_posix()
        lines.append(f"{rel}\t{st.st_size}\t{st.st_mtime_ns}")
    return "\n".join(lines) + "\n"


def assembly_stale(root: Path | None = None) -> bool:
    dest = local_dll_path(root)
    stamp = inputs_stamp(dest)
    if not dest.is_file() or not stamp.is_file():
        return True
    return stamp.read_text(encoding="utf-8") != inputs_fingerprint(root)


def ensure_compiled(root: Path | None = None) -> Path:
    """Compile on the ERP VM when Lab5.QMS C# (or the compiler) changed."""
    dest = local_dll_path(root)
    if not assembly_stale(root):
        return dest
    fingerprint = inputs_fingerprint(root)
    dest = compile_on_vm(root)
    inputs_stamp(dest).write_text(fingerprint, encoding="utf-8")
    return dest


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
    temp = ssh_run("$env:TEMP", host=inst.ssh).strip().splitlines()[-1].strip()
    if not temp:
        raise RuntimeError("remote $env:TEMP was empty")
    posix_temp = temp.replace("\\", "/")
    remote_zip = f"{posix_temp}/{REMOTE_ZIP}"
    remote_work = f"{temp}\\{REMOTE_DIR}"
    local_zip = dest.parent / REMOTE_ZIP
    local_zip.write_bytes(source_zip(root))
    try:
        _scp(str(local_zip), f"{inst.ssh}:{remote_zip}")
        ssh_run(
            "$ErrorActionPreference = 'Stop'; "
            f"$zip = '{temp}\\{REMOTE_ZIP}'; "
            f"$work = '{remote_work}'; "
            "if (Test-Path -LiteralPath $work) { "
            "Remove-Item -LiteralPath $work -Recurse -Force }; "
            "New-Item -ItemType Directory -Path $work | Out-Null; "
            "Expand-Archive -LiteralPath $zip -DestinationPath $work -Force; "
            "Set-Location -LiteralPath $work; "
            "& .\\build.ps1",
            host=inst.ssh,
        )
        remote_dll = f"{posix_temp}/{REMOTE_DIR}/bin/Release/{pack.ASSEMBLY_DLL}"
        _scp(f"{inst.ssh}:{remote_dll}", str(dest))
    finally:
        local_zip.unlink(missing_ok=True)
    if not dest.is_file():
        raise RuntimeError(f"DLL was not copied to {dest}")
    return dest


def main() -> None:
    path = ensure_compiled()
    print(path)


if __name__ == "__main__":
    main()
