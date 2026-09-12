#!/usr/bin/env -S uv run
"""Pack + publish Lab5.QMS, then prove the QMS/22.200.001 contract is live."""

from __future__ import annotations

import unittest

import acuqms.publish as pub
from acuqms.acu import ACU_INSTANCE_PATH, ssh_run
from acuqms.publish import (
    _ensure_qm_aspx_pages,
    _qm_aspx_names,
    _recycle_app_pool,
    qms_endpoint_live,
    wait_published,
)
from e2e.helper import (
    PACKAGE_NAME,
    QMS_ENDPOINT,
    QMS_VERSION,
    client,
    ensure_published,
    instance,
    qms_get,
)


class TestPublishAndPresence(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.status = ensure_published()

    def test_lab5_qms_is_published(self) -> None:
        with client() as session:
            names = session.customization_published()
        self.assertIn(PACKAGE_NAME, names)

    def test_entity_lists_qms_endpoint(self) -> None:
        with client() as session:
            endpoints = session.list_endpoints()
        self.assertIn(("QMS", QMS_VERSION), endpoints)

    def test_qms_swagger_200(self) -> None:
        with client() as session:
            r = session._checked(
                session._http.get(f"/entity/{QMS_ENDPOINT}/swagger.json")
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        paths = str(body.get("paths", {}))
        self.assertTrue(
            "InspectionPlan" in r.text or "InspectionPlan" in paths,
            "swagger missing InspectionPlan",
        )
        self.assertTrue(
            "StockItem" in r.text or "StockItem" in paths,
            "swagger missing StockItem",
        )
        self.assertTrue(
            "QMSSetup" in r.text or "QMSSetup" in paths,
            "swagger missing QMSSetup",
        )

    def test_inspection_plan_list(self) -> None:
        self._assert_entity_list("InspectionPlan")

    def test_inspection_order_list(self) -> None:
        self._assert_entity_list("InspectionOrder")

    def test_non_conformance_list(self) -> None:
        self._assert_entity_list("NonConformance")

    def test_stock_item_list(self) -> None:
        self._assert_entity_list("StockItem")

    def test_qms_setup_list(self) -> None:
        self._assert_entity_list("QMSSetup")

    def test_skip_path_entity_and_inspection_plan_json_array(self) -> None:
        """V18 / B8: after ensure_published, GET /entity lists QMS; InspectionPlan is JSON array.

        Holds on skip (`already published`) and on import+publish.
        """
        self.assertIn(self.status, ("already published", "published"))
        with client() as session:
            endpoints = session.list_endpoints()
            response = session._http.get(f"/entity/{QMS_ENDPOINT}/InspectionPlan")
        self.assertIn(("QMS", QMS_VERSION), endpoints)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        if self.status == "already published":
            self.assertIn(("QMS", QMS_VERSION), endpoints)
            self.assertIsInstance(response.json(), list)

    def _assert_entity_list(self, entity: str) -> None:
        with client() as session:
            rows = qms_get(session, entity, params={"$top": "1"})
        self.assertIsInstance(rows, list)


class TestAspxHashMismatchPublishV20(unittest.TestCase):
    def test_aspx_hash_mismatch_inspection_plan_200_without_manual_recycle(
        self,
    ) -> None:
        """V20 / B15: aspx recopy + recycle → InspectionPlan 200; test ! extra recycle."""
        inst = instance()
        if not inst.ssh:
            raise unittest.SkipTest("ACU_SSH empty — hosted path has no aspx scp")
        ensure_published()
        name = _qm_aspx_names()[0]
        win_dir = (ACU_INSTANCE_PATH + r"\Pages\QM").replace("'", "''")
        ssh_run(
            f"Set-Content -LiteralPath (Join-Path '{win_dir}' '{name}') "
            "-Value 'aspx-hash-mismatch' -Encoding ASCII"
        )
        pub._aspx_pages_ready = False
        try:
            _ensure_qm_aspx_pages()
            _recycle_app_pool()
            wait_published()
            with client() as session:
                self.assertTrue(qms_endpoint_live(session))
        finally:
            pub._aspx_pages_ready = False
            _ensure_qm_aspx_pages()


if __name__ == "__main__":
    unittest.main()
