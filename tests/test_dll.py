#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""Lab5.QMS.dll compile inputs + ensure-on-pack (V8 / I.pkg)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dll  # noqa: E402
from lab5_qms import pack  # noqa: E402

PX = ("PX.Data", "PX.Objects", "PX.Common", "PX.Common.Std", "PX.DbServices")


class TestCsprojPxHintPaths(unittest.TestCase):
    def test_hintpath_px_assemblies(self) -> None:
        root = ET.parse(ROOT / "src" / "Lab5.QMS" / "Lab5.QMS.csproj").getroot()
        self.assertEqual(
            (root.find("PropertyGroup/AcumaticaDir").text or "").strip(),
            r"C:\Acumatica\AcumaticaERP",
        )
        refs = {
            el.get("Include"): (el.find("HintPath").text or "").strip()
            for el in root.findall("ItemGroup/Reference")
            if el.find("HintPath") is not None
        }
        self.assertEqual(set(refs), set(PX))
        for name in PX:
            self.assertEqual(refs[name], rf"$(AcumaticaDir)\Bin\{name}.dll")
            private = root.find(f"ItemGroup/Reference[@Include='{name}']/Private")
            self.assertIsNotNone(private)
            self.assertEqual((private.text or "").strip().lower(), "false")


class TestDllScript(unittest.TestCase):
    def test_px_assemblies_match_csproj(self) -> None:
        self.assertEqual(dll.PX_ASSEMBLIES, PX)

    def test_build_ps1_uses_site_roslyn_csc(self) -> None:
        script = dll.build_ps1()
        self.assertIn(r"Bin\roslyn\csc.exe", script)
        self.assertIn("/target:library", script)
        self.assertIn(pack.ASSEMBLY_DLL, script)
        for name in PX:
            self.assertIn(name, script)

    def test_source_zip_has_cs_csproj_and_build_ps1(self) -> None:
        names = set()
        with zipfile.ZipFile(io.BytesIO(dll.source_zip(ROOT))) as zf:
            names = set(zf.namelist())
            script = zf.read("build.ps1").decode("utf-8")
        self.assertIn("Lab5.QMS.csproj", names)
        self.assertIn("build.ps1", names)
        self.assertIn("QMS.cs", names)
        self.assertIn("Graph/QMSInspectionPlanMaint.cs", names)
        self.assertTrue(
            all("obj/" not in name and "bin/" not in name for name in names)
        )
        self.assertIn(r"Bin\roslyn\csc.exe", script)
        self.assertGreaterEqual(len(dll.source_files(ROOT)), 20)

    def test_hosted_path_message(self) -> None:
        src = (ROOT / "dll.py").read_text(encoding="utf-8")
        self.assertIn("ACU_SSH empty — hosted path cannot compile Lab5.QMS.dll", src)
        self.assertNotIn("print(inst.password", src)
        self.assertNotIn("ACU_PASSWORD=", src)

    def test_makefile_has_no_dll_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertNotIn("\ndll:", makefile)
        self.assertNotIn("QMS_DLL", makefile)
        self.assertNotIn("pad-dll", makefile)
        self.assertIn("build: .venv", makefile)
        self.assertIn("deploy: .venv", makefile)
        self.assertNotIn("pack: dll", makefile)
        self.assertNotIn("\npack:", makefile)
        self.assertIn("check: test preflight ##", makefile)
        self.assertIn("release: test _release-gh", makefile)
        self.assertIn("python dll.py", makefile)
        self.assertIn("lab5-qms pack", makefile)
        self.assertIn("lab5-qms deploy", makefile)
        self.assertIn("ruff format --check", makefile)
        self.assertIn("ruff check", makefile)
        self.assertIn("python -u -m unittest discover -s tests", makefile)
        self.assertIn("clean: ##", makefile)
        self.assertIn("rm -rf src/Lab5.QMS/bin src/Lab5.QMS/obj", makefile)
        self.assertIn("rm -f Lab5_QMS_Customization.zip", makefile)
        self.assertIn("__pycache__", makefile)
        phony = makefile.split(".PHONY:", 1)[1].splitlines()[0]
        self.assertNotIn("dll", phony)
        self.assertIn("build", phony)
        self.assertNotIn("pack", phony)
        self.assertIn("deploy", phony)
        self.assertIn("clean", phony)

    def test_local_dll_path_release(self) -> None:
        self.assertEqual(
            dll.local_dll_path(ROOT),
            ROOT / "src" / "Lab5.QMS" / "bin" / "Release" / pack.ASSEMBLY_DLL,
        )

    def test_pack_publish_deploy_and_e2e_ensure_dll(self) -> None:
        cli_src = (ROOT / "lab5_qms" / "cli.py").read_text(encoding="utf-8")
        pack_src = (ROOT / "lab5_qms" / "pack.py").read_text(encoding="utf-8")
        helper = (ROOT / "e2e" / "helper.py").read_text(encoding="utf-8")
        self.assertIn("ensure_dll=True", cli_src)
        self.assertIn("ensure_dll=True", pack_src)
        self.assertIn("ensure_dll=True", helper)
        self.assertIn("def ensure_assembly", pack_src)
        self.assertIn("ensure_compiled", (ROOT / "dll.py").read_text(encoding="utf-8"))


class TestEnsureCompiled(unittest.TestCase):
    def test_fingerprint_covers_cs_csproj_and_compiler(self) -> None:
        text = dll.inputs_fingerprint(ROOT)
        self.assertIn("src/Lab5.QMS/QMS.cs\t", text)
        self.assertIn("src/Lab5.QMS/Graph/QMSInspectionPlanMaint.cs\t", text)
        self.assertIn("src/Lab5.QMS/Lab5.QMS.csproj\t", text)
        self.assertIn("dll.py\t", text)
        self.assertNotIn("Pages_QM/", text)
        self.assertNotIn("/bin/", text)
        self.assertNotIn("/obj/", text)

    def test_stale_when_dll_or_stamp_missing(self) -> None:
        missing = Path("/no/such/Lab5.QMS.dll")
        with patch.object(dll, "local_dll_path", return_value=missing):
            self.assertTrue(dll.assembly_stale(ROOT))
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / pack.ASSEMBLY_DLL
            dest.write_bytes(b"MZ")
            with patch.object(dll, "local_dll_path", return_value=dest):
                self.assertTrue(dll.assembly_stale(ROOT))

    def test_ensure_skips_compile_when_fingerprint_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / pack.ASSEMBLY_DLL
            dest.write_bytes(b"MZ")
            dll.inputs_stamp(dest).write_text(
                dll.inputs_fingerprint(ROOT), encoding="utf-8"
            )
            with (
                patch.object(dll, "local_dll_path", return_value=dest),
                patch.object(dll, "compile_on_vm") as compile,
            ):
                out = dll.ensure_compiled(ROOT)
            compile.assert_not_called()
            self.assertEqual(out, dest)

    def test_ensure_compiles_when_stale_and_writes_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / pack.ASSEMBLY_DLL
            dest.write_bytes(b"old")
            with (
                patch.object(dll, "local_dll_path", return_value=dest),
                patch.object(dll, "compile_on_vm", return_value=dest) as compile,
            ):
                out = dll.ensure_compiled(ROOT)
            compile.assert_called_once_with(ROOT)
            self.assertEqual(out, dest)
            stamp = dll.inputs_stamp(dest)
            self.assertTrue(stamp.is_file())
            self.assertEqual(
                stamp.read_text(encoding="utf-8"), dll.inputs_fingerprint(ROOT)
            )

    def test_package_zip_ensure_dll_calls_ensure_assembly(self) -> None:
        with patch.object(pack, "ensure_assembly") as ensure:
            pack.package_zip(ROOT, ensure_dll=True)
        ensure.assert_called_once_with(ROOT)
        with patch.object(pack, "ensure_assembly") as ensure:
            pack.package_zip(ROOT)
        ensure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
