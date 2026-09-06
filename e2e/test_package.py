#!/usr/bin/env -S uv run
"""Pack + publish Lab5.QMS, then prove the QMS/22.200.001 contract is live."""

from __future__ import annotations

import unittest

from e2e.helper import (
    PACKAGE_NAME,
    QMS_ENDPOINT,
    QMS_VERSION,
    client,
    ensure_published,
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
        self.assertTrue(
            "InspectionPlan" in r.text
            or "InspectionPlan" in str(body.get("paths", {})),
            "swagger missing InspectionPlan",
        )

    def test_inspection_plan_list(self) -> None:
        self._assert_entity_list("InspectionPlan")

    def test_inspection_order_list(self) -> None:
        self._assert_entity_list("InspectionOrder")

    def test_non_conformance_list(self) -> None:
        self._assert_entity_list("NonConformance")

    def _assert_entity_list(self, entity: str) -> None:
        with client() as session:
            rows = qms_get(session, entity, params={"$top": "1"})
        self.assertIsInstance(rows, list)


if __name__ == "__main__":
    unittest.main()
