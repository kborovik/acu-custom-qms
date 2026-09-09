#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T34 / V16: GenericInquiryScreen QM401000 Quality Queue."""

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

GI_XML = ROOT / "_project" / "GenericInquiryScreen_QM401000.xml"
FORBIDDEN_ACTIONS = (
    "EvaluateResults",
    "ReleaseLotDecision",
    "CloseNCR",
    "DispositionRTV",
)
COLUMNS = (
    "Inventory",
    "Lot",
    "Receipt",
    "Vendor",
    "Plan",
    "Lot Status",
    "Order Nbr",
    "Order Status",
    "NCR Nbr",
    "NCR Status",
)


def _zip() -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(pack.package_zip(ROOT)))


class TestQualityQueueGI(unittest.TestCase):
    def test_gi_xml_work_row_drills_and_no_actions(self) -> None:
        tree = ET.parse(GI_XML)
        root = tree.getroot()
        self.assertEqual(root.tag, "GenericInquiryScreen")
        self.assertEqual(root.get("ScreenID"), "QM401000")
        blob = ET.tostring(root, encoding="unicode")
        for action in FORBIDDEN_ACTIONS:
            self.assertNotIn(action, blob, action)
        self.assertNotIn("Evaluate", blob)
        design = root.find(".//{*}GIDesign/{*}row")
        if design is None:
            design = root.find(".//GIDesign/row")
        self.assertIsNotNone(design)
        self.assertEqual(design.get("Name"), "Quality Queue")
        self.assertEqual(design.get("MassActionsOnRecordsEnabled"), "0")
        tables = {
            row.get("Alias"): row.get("Name")
            for row in root.findall(".//{*}GITable") + root.findall(".//GITable")
        }
        self.assertEqual(tables.get("Order"), "Lab5.QMS.QMSInspectionOrder")
        self.assertEqual(tables.get("NCR"), "Lab5.QMS.QMSNonConformance")
        self.assertIn("INLotSerialStatusByCostCenter", tables.get("Lot") or "")
        captions = [
            row.get("Caption")
            for row in root.findall(".//{*}GIResult") + root.findall(".//GIResult")
            if row.get("Caption")
        ]
        for caption in COLUMNS:
            self.assertIn(caption, captions, caption)
        where = ET.tostring(
            root.find(".//{*}data")
            if root.find(".//{*}data") is not None
            else root.find(".//data"),
            encoding="unicode",
        )
        self.assertIn("QC Hold", where)
        self.assertIn('Condition="NE"', where)
        self.assertIn('Value1="C"', where)
        self.assertIn('Condition="NN"', where)
        links = {
            row.get("Link")
            for row in root.findall(".//{*}GINavigationScreen")
            + root.findall(".//GINavigationScreen")
        }
        self.assertEqual(links, {"QM301000", "QM302000"})

    def test_packed_project_has_generic_inquiry_screen(self) -> None:
        with _zip() as zf:
            project = ET.fromstring(zf.read("project.xml"))
            names = set(zf.namelist())
        gi = project.find("GenericInquiryScreen")
        self.assertIsNotNone(gi)
        self.assertEqual(gi.get("ScreenID"), "QM401000")
        self.assertIn("_project/GenericInquiryScreen_QM401000.xml", names)
        blob = ET.tostring(gi, encoding="unicode")
        for action in FORBIDDEN_ACTIONS:
            self.assertNotIn(action, blob, action)
        self.assertNotIn(
            "FrontendSources/screen/src/screens/QM/QM401000/",
            " ".join(names),
        )


if __name__ == "__main__":
    unittest.main()
