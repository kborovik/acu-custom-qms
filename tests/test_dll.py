#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""gmake dll: csproj PX refs + SSH compile inputs (V8 / I.pkg)."""

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

import dll  # noqa: E402
from lab5_qms import pack  # noqa: E402

PX = ("PX.Data", "PX.Objects", "PX.Common", "PX.Common.Std")


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
            private = root.find(
                f"ItemGroup/Reference[@Include='{name}']/Private"
            )
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
        self.assertTrue(all("obj/" not in name and "bin/" not in name for name in names))
        self.assertIn(r"Bin\roslyn\csc.exe", script)
        self.assertGreaterEqual(len(dll.source_files(ROOT)), 20)

    def test_hosted_path_message(self) -> None:
        src = (ROOT / "dll.py").read_text(encoding="utf-8")
        self.assertIn("ACU_SSH empty — hosted path cannot compile Lab5.QMS.dll", src)
        self.assertNotIn("print(inst.password", src)
        self.assertNotIn("ACU_PASSWORD=", src)

    def test_makefile_dll_recipe(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn(
            "QMS_DLL := src/Lab5.QMS/bin/Release/Lab5.QMS.dll", makefile
        )
        self.assertIn("dll: $(QMS_DLL)", makefile)
        self.assertIn("pack: dll", makefile)
        self.assertIn("check: test preflight $(QMS_DLL)", makefile)
        self.assertIn("release: test $(QMS_DLL)", makefile)
        self.assertIn("$(QMS_DLL): | .venv", makefile)
        self.assertIn("python dll.py", makefile)
        self.assertIn("lab5-qms pack", makefile)
        self.assertIn("python -u -m unittest discover -s tests", makefile)
        self.assertIn("clean: ##", makefile)
        self.assertIn("rm -rf src/Lab5.QMS/bin src/Lab5.QMS/obj", makefile)
        self.assertIn("rm -f Lab5_QMS_Customization.zip", makefile)
        self.assertIn("__pycache__", makefile)
        phony = makefile.split(".PHONY:", 1)[1].splitlines()[0]
        self.assertIn("dll", phony)
        self.assertIn("clean", phony)
        self.assertNotIn("QMS_DLL", phony)

    def test_local_dll_path_release(self) -> None:
        self.assertEqual(
            dll.local_dll_path(ROOT),
            ROOT / "src" / "Lab5.QMS" / "bin" / "Release" / pack.ASSEMBLY_DLL,
        )


if __name__ == "__main__":
    unittest.main()
