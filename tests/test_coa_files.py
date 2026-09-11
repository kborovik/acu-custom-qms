#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T9 / V2 / V3 / I.files: attach CoA PDF + JSON via /files on InspectionOrder NoteID."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionOrder.cs"
RULES_CS = ROOT / "QMS" / "Lab5.QMS" / "QMSCoAFileRules.cs"
HTML = (
    ROOT
    / "QMS"
    / "FrontendSources"
    / "screen"
    / "src"
    / "development"
    / "screens"
    / "QM"
    / "QM301000"
    / "QM301000.html"
)
TS = (
    ROOT
    / "QMS"
    / "FrontendSources"
    / "screen"
    / "src"
    / "development"
    / "screens"
    / "QM"
    / "QM301000"
    / "QM301000.ts"
)
ENDPOINT_XML = ROOT / "QMS" / "_project" / "QMS.xml"
SQL = ROOT / "QMS" / "SQL" / "CreateQMSTables.sql"
QMS_CS = ROOT / "QMS" / "Lab5.QMS" / "QMS.cs"

PDF = ".pdf"
JSON = ".json"
ENDPOINT = "QMS"
VERSION = "22.200.001"


def files_path(inspection_order_nbr: str, file_name: str) -> str:
    return f"/entity/{ENDPOINT}/{VERSION}/InspectionOrder/{inspection_order_nbr}/files/{file_name}"


def has_extension(file_name: str | None, extension: str | None) -> bool:
    if not file_name or not extension:
        return False
    return file_name.lower().endswith(extension.lower())


def is_coa_pdf(file_name: str | None) -> bool:
    return has_extension(file_name, PDF)


def is_parsed_json(file_name: str | None) -> bool:
    return has_extension(file_name, JSON)


def has_system_of_record(file_names: list[str] | None) -> bool:
    if file_names is None:
        return False
    pdf = any(is_coa_pdf(name) for name in file_names)
    json = any(is_parsed_json(name) for name in file_names)
    return pdf and json


class TestOrderNoteIdFilesLinkV2(unittest.TestCase):
    def test_dac_pxnote_on_noteid(self) -> None:
        src = ORDER_CS.read_text(encoding="utf-8")
        region = src.split("#region NoteID", 1)[1].split("#endregion", 1)[0]
        self.assertIn("[PXNote]", region)
        self.assertIn("public virtual Guid? NoteID { get; set; }", region)

    def test_sql_noteid_on_order(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        start = sql.index("CREATE TABLE [dbo].[UsrQMSInspectionOrder]")
        end = sql.find("CREATE TABLE", start + 1)
        block = sql[start:] if end < 0 else sql[start:end]
        self.assertIn("[NoteID] [uniqueidentifier] NULL", block)

    def test_rest_files_path(self) -> None:
        self.assertEqual(
            files_path("QORD-000001", "COA-GL-2026-09182.pdf"),
            "/entity/QMS/22.200.001/InspectionOrder/QORD-000001/files/COA-GL-2026-09182.pdf",
        )
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static string FilesPath(string inspectionOrderNbr, string fileName)",
            src,
        )
        self.assertIn('"/entity/" + QMS.EndpointName + "/" + QMS.EndpointVersion', src)
        self.assertIn(
            '"/InspectionOrder/" + inspectionOrderNbr + "/files/" + fileName', src
        )
        qms = QMS_CS.read_text(encoding="utf-8")
        self.assertIn('EndpointName = "QMS"', qms)
        self.assertIn('EndpointVersion = "22.200.001"', qms)


class TestRestNoteIdAndExpandFilesV2(unittest.TestCase):
    def test_endpoint_exposes_noteid(self) -> None:
        xml = ENDPOINT_XML.read_text(encoding="utf-8")
        self.assertIn('<Field name="NoteID" type="GuidValue" />', xml)
        self.assertIn('<Mapping field="NoteID">', xml)
        self.assertIn('field="NoteID"', xml)
        self.assertIn(
            "PUT /entity/QMS/22.200.001/InspectionOrder/{InspectionOrderNbr}/files/{fileName}",
            xml,
        )
        self.assertIn("GET ?$expand=files", xml)
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn('public const string ExpandFiles = "files"', src)


class TestScreenPaperclipV3(unittest.TestCase):
    def test_order_form_files_indicator(self) -> None:
        html = HTML.read_text(encoding="utf-8")
        ts = TS.read_text(encoding="utf-8")
        self.assertIn('view.bind="Document"', html)
        self.assertIn("hideFilesIndicator: false", ts)
        self.assertIn("hideNotesIndicator: false", ts)


class TestSystemOfRecordAttachmentsV3(unittest.TestCase):
    def test_pdf_and_json_present(self) -> None:
        self.assertTrue(
            has_system_of_record(["COA-GL-2026-09182.pdf", "COA-GL-2026-09182.json"])
        )
        self.assertTrue(
            has_system_of_record(["audit.JSON", "original.PDF", "notes.txt"])
        )

    def test_missing_pdf_or_json(self) -> None:
        self.assertFalse(has_system_of_record(["COA-GL-2026-09182.pdf"]))
        self.assertFalse(has_system_of_record(["COA-GL-2026-09182.json"]))
        self.assertFalse(has_system_of_record([]))
        self.assertFalse(has_system_of_record(None))
        self.assertFalse(has_system_of_record(["notes.txt", "image.png"]))

    def test_csharp_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn('public const string PdfExtension = ".pdf"', src)
        self.assertIn('public const string JsonExtension = ".json"', src)
        self.assertIn(
            "public static bool HasSystemOfRecord(IEnumerable<string> fileNames)",
            src,
        )
        self.assertIn("if (fileNames == null)", src)
        self.assertIn(
            "fileName.EndsWith(extension, StringComparison.OrdinalIgnoreCase)", src
        )
        self.assertIn("return pdf && json;", src)


if __name__ == "__main__":
    unittest.main()
