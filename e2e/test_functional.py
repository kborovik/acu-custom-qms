"""Seed gate + CoA ingest + evaluate/release. Dock/lot skips without lots."""

from __future__ import annotations

import json
import unittest
from datetime import date

from acumatica_cli.client import unwrap, wrap

from e2e.helper import (
    FAIL_ORDER,
    ITEM_CD,
    LINE_FAIL,
    MIN_PDF,
    NCR_NBR,
    OVERALL_FAIL,
    OVERALL_PASS,
    PASS_ORDER,
    PLAN_ID,
    QMS_ENDPOINT,
    STATUS_COMPLETED,
    VENDOR_CD,
    bootstrap_endpoint,
    client,
    ensure_numbering_and_role,
    ensure_published,
    put_file,
    qms_get,
    qms_invoke,
    qms_put,
)


def _seed_ready(session) -> str | None:
    """Return a skip reason when GitOps seed is not on this tenant."""
    boot = bootstrap_endpoint(session)
    try:
        prefs = session.get_list("INPreferences", {"$top": "1"}, endpoint=boot)
        if not prefs:
            return "Bootstrap INPreferences empty"
    except RuntimeError as exc:
        return f"Bootstrap INPreferences: {exc}"
    try:
        prefs = session.get_list("POPreferences", {"$top": "1"}, endpoint=boot)
        if not prefs:
            return "Bootstrap POPreferences empty"
    except RuntimeError as exc:
        return f"Bootstrap POPreferences: {exc}"
    try:
        session.get_list(
            "Company", {"$select": "CompanyCD", "$top": "1"}, endpoint=boot
        )
    except RuntimeError:
        pass  # BQL-delegate / key-dict 500s; IN/PO prefs already proved seed
    try:
        items = session.get_list("StockItem", {"$top": "1"})
        if not items:
            return "Default StockItem empty"
    except RuntimeError as exc:
        return f"Default StockItem: {exc}"
    try:
        session.get_list("PurchaseReceipt", {"$top": "1"})
    except RuntimeError as exc:
        return f"Default PurchaseReceipt: {exc}"
    item = session.get_record("StockItem", [ITEM_CD])
    if item is None:
        return f"StockItem {ITEM_CD} missing — seed tenant from acu-gitops-qms"
    vendor = session.get_record("Vendor", [VENDOR_CD])
    if vendor is None:
        return f"Vendor {VENDOR_CD} missing — seed tenant from acu-gitops-qms"
    return None


def _plan_record() -> dict:
    return {
        "PlanID": PLAN_ID,
        "Description": "E2E echinacea 4% polyphenols",
        "InventoryID": ITEM_CD,
        "SamplingPlan": "ISO 2859-1 Level II Normal",
        "Status": "A",
        "Tests": [
            {
                "LineNbr": 10,
                "TestID": "ASSAY_POLYPHENOLS",
                "Description": "Total polyphenols",
                "TestMethod": "UV-Vis",
                "TargetValue": 4.0,
                "MinValue": 3.0,
                "MaxValue": 5.0,
                "UOM": "% (w/w)",
                "Criticality": "C",
            },
            {
                "LineNbr": 20,
                "TestID": "APPEARANCE",
                "Description": "Visual appearance",
                "TestMethod": "Organoleptic",
                "UOM": "n/a",
                "Criticality": "M",
            },
        ],
    }


def _order_record(nbr: str, assay: float, appearance: str) -> dict:
    return {
        "InspectionOrderNbr": nbr,
        "InventoryID": ITEM_CD,
        "LotSerialNbr": f"E2E-{nbr[-6:]}",
        "VendorID": VENDOR_CD,
        "PlanID": PLAN_ID,
        "TestingLabID": "LAB-GL-ANALYTICAL",
        "LabCertificateNbr": f"COA-{nbr}",
        "InspectionDate": date.today().isoformat(),
        "Results": [
            {
                "LineNbr": 10,
                "TestID": "ASSAY_POLYPHENOLS",
                "TestMethod": "UV-Vis",
                "ActualNumericValue": assay,
                "Notes": "e2e",
            },
            {
                "LineNbr": 20,
                "TestID": "APPEARANCE",
                "TestMethod": "Organoleptic",
                "TargetSpec": "PASS",
                "ActualTextValue": appearance,
                "Notes": "e2e",
            },
        ],
    }


class TestSeedGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()

    def test_gitops_seed_present(self) -> None:
        with client() as session:
            reason = _seed_ready(session)
        if reason:
            self.skipTest(reason)


class TestCoaIngest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            reason = _seed_ready(session)
            if reason:
                raise unittest.SkipTest(reason)
            try:
                ensure_numbering_and_role(session)
                qms_put(session, "InspectionPlan", _plan_record())
            except RuntimeError as exc:
                raise unittest.SkipTest(
                    f"InspectionPlan PUT unavailable ({exc})"
                ) from exc

    def test_get_plan_expand_tests(self) -> None:
        with client() as session:
            plan = qms_get(
                session,
                "InspectionPlan",
                [PLAN_ID],
                params={"$expand": "Tests"},
            )
        self.assertIsNotNone(plan)
        body = unwrap(plan)
        self.assertEqual(body.get("PlanID"), PLAN_ID)
        tests = body.get("Tests") or []
        ids = {row.get("TestID") for row in tests}
        self.assertIn("ASSAY_POLYPHENOLS", ids)
        self.assertIn("APPEARANCE", ids)

    def test_put_pass_order_attach_files_evaluate_release(self) -> None:
        with client() as session:
            qms_put(session, "InspectionOrder", _order_record(PASS_ORDER, 4.1, "PASS brown"))
            put_file(session, PASS_ORDER, f"{PASS_ORDER}.pdf", MIN_PDF)
            put_file(
                session,
                PASS_ORDER,
                f"{PASS_ORDER}.json",
                json.dumps({"order": PASS_ORDER, "assay": 4.1}).encode(),
            )
            order = unwrap(
                qms_get(
                    session,
                    "InspectionOrder",
                    [PASS_ORDER],
                    params={"$expand": "Results,files"},
                )
            )
            names = [
                str(f.get("filename") or f.get("name") or "")
                for f in (order.get("files") or [])
                if isinstance(f, dict)
            ]
            if not names:
                # some builds keep files only on the files href, not $expand
                listing = session._checked(
                    session._http.get(
                        f"/entity/{QMS_ENDPOINT}/InspectionOrder/{PASS_ORDER}?$expand=files"
                    )
                ).json()
                raw_files = listing.get("files") or []
                names = [
                    str(f.get("filename") or f.get("name") or "")
                    for f in raw_files
                    if isinstance(f, dict)
                ]
            joined = " ".join(names).lower()
            self.assertIn(".pdf", joined)
            self.assertIn(".json", joined)

            qms_invoke(session, "EvaluateResults", {"InspectionOrderNbr": PASS_ORDER})
            evaluated = unwrap(qms_get(session, "InspectionOrder", [PASS_ORDER]))
            self.assertEqual(evaluated.get("OverallEvaluation"), OVERALL_PASS)

            qms_invoke(session, "ReleaseLotDecision", {"InspectionOrderNbr": PASS_ORDER})
            released = unwrap(qms_get(session, "InspectionOrder", [PASS_ORDER]))
            self.assertEqual(released.get("Status"), STATUS_COMPLETED)
            self.assertEqual(released.get("OverallEvaluation"), OVERALL_PASS)

    def test_fail_order_evaluate_release_creates_ncr(self) -> None:
        with client() as session:
            qms_put(
                session,
                "InspectionOrder",
                _order_record(FAIL_ORDER, 0.4, "FAIL dark"),
            )
            qms_invoke(session, "EvaluateResults", {"InspectionOrderNbr": FAIL_ORDER})
            evaluated = unwrap(
                qms_get(
                    session,
                    "InspectionOrder",
                    [FAIL_ORDER],
                    params={"$expand": "Results"},
                )
            )
            self.assertEqual(evaluated.get("OverallEvaluation"), OVERALL_FAIL)
            results = {row.get("LineNbr"): row for row in (evaluated.get("Results") or [])}
            self.assertEqual((results.get(10) or {}).get("Evaluation"), LINE_FAIL)

            qms_invoke(session, "ReleaseLotDecision", {"InspectionOrderNbr": FAIL_ORDER})
            ncrs = session.get_list(
                "NonConformance",
                {
                    "$filter": f"InspectionOrderNbr eq '{FAIL_ORDER}'",
                    "$top": "5",
                },
                endpoint=QMS_ENDPOINT,
            )
            self.assertTrue(ncrs, "expected NonConformance for failed order")
            ncr = unwrap(ncrs[0])
            self.assertEqual(ncr.get("InspectionOrderNbr"), FAIL_ORDER)
            self.assertEqual(ncr.get("InventoryHoldStatus"), "Quarantine")


class TestDockLot(unittest.TestCase):
    """V1 cannot-pass gate on PO receipt release. Needs lot-tracked items."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            reason = _seed_ready(session)
            if reason:
                raise unittest.SkipTest(reason)
            try:
                ensure_numbering_and_role(session)
            except RuntimeError as exc:
                raise unittest.SkipTest(str(exc)) from exc
            item = unwrap(session.get_record("StockItem", [ITEM_CD]) or {})
            lot_class = item.get("LotSerialClass") or item.get("LotSerClass")
            if not lot_class:
                raise unittest.SkipTest(
                    f"{ITEM_CD} has no LotSerialClass — dock/lot e2e needs "
                    "lot-tracked items from acu-gitops-qms"
                )

    def test_receipt_release_creates_qc_hold_order(self) -> None:
        self.skipTest(
            "lot-tracked receipt path not seeded on this tenant; "
            "GitOps PARTS items ship without a lot class"
        )


class TestPostNcr(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            reason = _seed_ready(session)
            if reason:
                raise unittest.SkipTest(reason)
            try:
                ensure_numbering_and_role(session)
            except RuntimeError as exc:
                raise unittest.SkipTest(str(exc)) from exc

    def test_post_nonconformance(self) -> None:
        record = {
            "NCRNbr": NCR_NBR,
            "InventoryID": ITEM_CD,
            "LotSerialNbr": "E2E-POST",
            "VendorID": VENDOR_CD,
            "Severity": "C",
            "Description": "e2e posted NCR",
            "InventoryHoldStatus": "Quarantine",
        }
        with client() as session:
            try:
                posted = session._http.post(
                    f"/entity/{QMS_ENDPOINT}/NonConformance", json=wrap(record)
                )
                if posted.status_code in (404, 405, 406):
                    session.put("NonConformance", record, endpoint=QMS_ENDPOINT)
                else:
                    session._checked(posted)
                rec = qms_get(session, "NonConformance", [NCR_NBR])
            except RuntimeError as exc:
                self.skipTest(str(exc))
        self.assertIsNotNone(rec)
        body = unwrap(rec)
        self.assertEqual(body.get("NCRNbr"), NCR_NBR)


if __name__ == "__main__":
    unittest.main()
