#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T8 / T20 / T22 / V2 / V12 / V13: REST endpoint QMS/22.200.001 InspectionPlan GET/PUT, InspectionOrder GET/PUT, NonConformance GET/POST, StockItem GET/PUT."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT_XML = ROOT / "_project" / "QMS.xml"
QMS_CS = ROOT / "src" / "Lab5.QMS" / "QMS.cs"
NS = "{http://www.acumatica.com/entity/maintenance/5.31}"

ENTITY_VERBS = {
    "InspectionPlan": ("GET", "PUT"),
    "InspectionOrder": ("GET", "PUT"),
    "NonConformance": ("GET", "POST"),
    "StockItem": ("GET", "PUT"),
}

INSPECTION_PLAN_FIELDS = {
    "PlanID": "StringValue",
    "Description": "StringValue",
    "InventoryID": "StringValue",
    "SamplingPlan": "StringValue",
    "Status": "StringValue",
    "Tests": "InspectionPlanTest[]",
}

INSPECTION_PLAN_TEST_FIELDS = {
    "LineNbr": "IntValue",
    "TestID": "StringValue",
    "Description": "StringValue",
    "TestMethod": "StringValue",
    "TargetValue": "DecimalValue",
    "MinValue": "DecimalValue",
    "MaxValue": "DecimalValue",
    "UOM": "StringValue",
    "Criticality": "StringValue",
}

INSPECTION_ORDER_FIELDS = {
    "InspectionOrderNbr": "StringValue",
    "Status": "StringValue",
    "InventoryID": "StringValue",
    "LotSerialNbr": "StringValue",
    "VendorID": "StringValue",
    "ReceiptNbr": "StringValue",
    "PlanID": "StringValue",
    "TestingLabID": "StringValue",
    "LabCertificateNbr": "StringValue",
    "InspectionDate": "DateTimeValue",
    "OverallEvaluation": "StringValue",
    "NoteID": "GuidValue",
    "Results": "InspectionOrderResult[]",
}

INSPECTION_ORDER_RESULT_FIELDS = {
    "LineNbr": "IntValue",
    "TestID": "StringValue",
    "TestMethod": "StringValue",
    "TargetSpec": "StringValue",
    "ActualNumericValue": "DecimalValue",
    "ActualTextValue": "StringValue",
    "Evaluation": "StringValue",
    "Notes": "StringValue",
}

NON_CONFORMANCE_FIELDS = {
    "NCRNbr": "StringValue",
    "InspectionOrderNbr": "StringValue",
    "InventoryID": "StringValue",
    "LotSerialNbr": "StringValue",
    "VendorID": "StringValue",
    "ReceiptNbr": "StringValue",
    "Severity": "StringValue",
    "NonConformanceType": "StringValue",
    "RootCauseCategory": "StringValue",
    "Description": "StringValue",
    "ActionRequired": "StringValue",
    "InventoryHoldStatus": "StringValue",
}

STOCK_ITEM_FIELDS = {
    "InventoryID": "StringValue",
    "UsrQMSInspectionRequired": "BooleanValue",
    "UsrQMSInspectionPlanID": "StringValue",
    "UsrMinShelfLifeDays": "IntValue",
}

STOCK_ITEM_MAPPINGS = {
    "InventoryID": ("Item", "InventoryCD"),
    "UsrQMSInspectionRequired": ("Item", "UsrQMSInspectionRequired"),
    "UsrQMSInspectionPlanID": ("Item", "UsrQMSInspectionPlanID"),
    "UsrMinShelfLifeDays": ("Item", "UsrMinShelfLifeDays"),
}


def _endpoint() -> ET.Element:
    root = ET.parse(ENDPOINT_XML).getroot()
    self_check = root.tag == "EntityEndpoint"
    if not self_check:
        raise AssertionError(f"expected EntityEndpoint root, got {root.tag}")
    endpoint = root.find(f"{NS}Endpoint")
    if endpoint is None:
        raise AssertionError("missing Endpoint child")
    return endpoint


def _fields(entity: ET.Element) -> dict[str, str]:
    return {
        field.get("name"): field.get("type")
        for field in entity.findall(f"{NS}Fields/{NS}Field")
    }


def _mappings(entity: ET.Element) -> dict[str, tuple[str | None, str | None]]:
    out: dict[str, tuple[str | None, str | None]] = {}
    for mapping in entity.findall(f"{NS}Mappings/{NS}Mapping"):
        to = mapping.find(f"{NS}To")
        out[mapping.get("field")] = (
            None if to is None else to.get("object"),
            None if to is None else to.get("field"),
        )
    return out


def _nested_mappings(entity: ET.Element, field: str) -> dict[str, tuple[str | None, str | None]]:
    """Detail field maps nest under the parent collection Mapping (Detail has no Mappings)."""
    out: dict[str, tuple[str | None, str | None]] = {}
    for mapping in entity.findall(f"{NS}Mappings/{NS}Mapping"):
        if mapping.get("field") != field:
            continue
        for child in mapping.findall(f"{NS}Mapping"):
            to = child.find(f"{NS}To")
            out[child.get("field")] = (
                None if to is None else to.get("object"),
                None if to is None else to.get("field"),
            )
    return out


def _top(name: str) -> ET.Element:
    endpoint = _endpoint()
    for entity in endpoint.findall(f"{NS}TopLevelEntity"):
        if entity.get("name") == name:
            return entity
    raise AssertionError(f"missing TopLevelEntity {name}")


def _detail(name: str) -> ET.Element:
    endpoint = _endpoint()
    for entity in endpoint.findall(f"{NS}Detail"):
        if entity.get("name") == name:
            return entity
    raise AssertionError(f"missing Detail {name}")


class TestQmsEndpointIdentityV2(unittest.TestCase):
    def test_endpoint_name_version_contract(self) -> None:
        endpoint = _endpoint()
        self.assertEqual(endpoint.get("name"), "QMS")
        self.assertEqual(endpoint.get("version"), "22.200.001")
        self.assertEqual(endpoint.get("systemContractVersion"), "4")
        src = QMS_CS.read_text(encoding="utf-8")
        self.assertIn('EndpointName = "QMS"', src)
        self.assertIn('EndpointVersion = "22.200.001"', src)

    def test_i_rest_entities_and_verbs(self) -> None:
        endpoint = _endpoint()
        names = {e.get("name") for e in endpoint.findall(f"{NS}TopLevelEntity")}
        self.assertEqual(names, set(ENTITY_VERBS))
        xml = ENDPOINT_XML.read_text(encoding="utf-8")
        for entity, verbs in ENTITY_VERBS.items():
            self.assertIn(entity, xml)
            self.assertIn(" ".join(verbs), xml)


class TestInspectionPlanGetPutV12(unittest.TestCase):
    def test_screen_and_plan_fields(self) -> None:
        plan = _top("InspectionPlan")
        self.assertEqual(plan.get("screen"), "QM201000")
        self.assertEqual(_fields(plan), INSPECTION_PLAN_FIELDS)

    def test_tests_expand_detail(self) -> None:
        plan = _top("InspectionPlan")
        mappings = _mappings(plan)
        self.assertEqual(mappings["Tests"], ("Tests", ""))
        tests = _detail("InspectionPlanTest")
        self.assertEqual(_fields(tests), INSPECTION_PLAN_TEST_FIELDS)
        self.assertEqual(_mappings(tests), {})
        test_maps = _nested_mappings(plan, "Tests")
        for name in INSPECTION_PLAN_TEST_FIELDS:
            self.assertEqual(test_maps[name], ("Tests", name))

    def test_plan_header_maps_to_document(self) -> None:
        mappings = _mappings(_top("InspectionPlan"))
        for name in ("PlanID", "Description", "InventoryID", "SamplingPlan", "Status"):
            self.assertEqual(mappings[name], ("Document", name))


class TestInspectionOrderPutV2(unittest.TestCase):
    def test_screen_and_order_fields(self) -> None:
        order = _top("InspectionOrder")
        self.assertEqual(order.get("screen"), "QM301000")
        self.assertEqual(_fields(order), INSPECTION_ORDER_FIELDS)

    def test_results_detail_for_coa_ingest(self) -> None:
        order = _top("InspectionOrder")
        mappings = _mappings(order)
        self.assertEqual(mappings["Results"], ("Results", ""))
        for name in (
            "Status",
            "TestingLabID",
            "LabCertificateNbr",
            "InspectionDate",
            "OverallEvaluation",
            "NoteID",
        ):
            self.assertEqual(mappings[name], ("Document", name))
        actions = {
            action.get("name"): action.get("mappedTo")
            for action in order.findall(f"{NS}Actions/{NS}Action")
        }
        self.assertEqual(
            actions,
            {
                "EvaluateResults": "EvaluateResults",
                "ReleaseLotDecision": "ReleaseLotDecision",
            },
        )
        results = _detail("InspectionOrderResult")
        self.assertEqual(_fields(results), INSPECTION_ORDER_RESULT_FIELDS)
        self.assertEqual(_mappings(results), {})
        result_maps = _nested_mappings(order, "Results")
        for name in INSPECTION_ORDER_RESULT_FIELDS:
            self.assertEqual(result_maps[name], ("Results", name))


class TestNonConformancePostV2(unittest.TestCase):
    def test_screen_and_ncr_fields(self) -> None:
        ncr = _top("NonConformance")
        self.assertEqual(ncr.get("screen"), "QM302000")
        self.assertEqual(_fields(ncr), NON_CONFORMANCE_FIELDS)
        mappings = _mappings(ncr)
        for name in NON_CONFORMANCE_FIELDS:
            self.assertEqual(mappings[name], ("Document", name))


class TestStockItemUsrFieldsV13(unittest.TestCase):
    def test_screen_and_usr_fields(self) -> None:
        item = _top("StockItem")
        self.assertEqual(item.get("screen"), "IN202500")
        self.assertEqual(_fields(item), STOCK_ITEM_FIELDS)
        mappings = _mappings(item)
        for name, mapped in STOCK_ITEM_MAPPINGS.items():
            self.assertEqual(mappings[name], mapped, name)


if __name__ == "__main__":
    unittest.main()
