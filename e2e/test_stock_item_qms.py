#!/usr/bin/env -S uv run
"""T23 / V13: QMS StockItem PUT persist + GET roundtrip; GitOps six-item shape."""

from __future__ import annotations

import unittest

from e2e.helper import (
    DB_NAME,
    ITEM_CD,
    USR_ITEM_COLUMNS,
    client,
    company_id,
    ensure_numbering_and_role,
    ensure_published,
    instance,
    qms_get,
    qms_put,
    sql_lines,
    unwrap,
)
from e2e.test_functional import GITOPS_PLANS, _seed_ready

# GitOps acu-gitops-qms config/qms/20-stock-item-qms.yaml PUT shape (V13).
# This repo must not `acu apply` that YAML; e2e PUTs the same field set on
# QMS/22.200.001 (sibling endpoint: line is out of scope).
GITOPS_STOCK_ITEMS: tuple[dict, ...] = (
    {
        "InventoryID": "RAW-ECH-EXT4",
        "UsrQMSInspectionRequired": True,
        "UsrQMSInspectionPlanID": "PLAN-ECH-EXT4",
        "UsrMinShelfLifeDays": 180,
    },
    {
        "InventoryID": "RAW-ELD-EXT10",
        "UsrQMSInspectionRequired": True,
        "UsrQMSInspectionPlanID": "PLAN-ELD-EXT10",
        "UsrMinShelfLifeDays": 180,
    },
    {
        "InventoryID": "RAW-ASH-EXT5",
        "UsrQMSInspectionRequired": True,
        "UsrQMSInspectionPlanID": "PLAN-ASH-EXT5",
        "UsrMinShelfLifeDays": 180,
    },
    {
        "InventoryID": "RAW-COQ10-99",
        "UsrQMSInspectionRequired": True,
        "UsrQMSInspectionPlanID": "PLAN-COQ10-99",
        "UsrMinShelfLifeDays": 365,
    },
    {
        "InventoryID": "RAW-OMEGA3-70",
        "UsrQMSInspectionRequired": True,
        "UsrQMSInspectionPlanID": "PLAN-OMEGA3-70",
        "UsrMinShelfLifeDays": 270,
    },
    {
        "InventoryID": "RAW-ASTA-10",
        "UsrQMSInspectionRequired": True,
        "UsrQMSInspectionPlanID": "PLAN-ASTA-10",
        "UsrMinShelfLifeDays": 270,
    },
)


def _sql_usr(inventory_cd: str) -> tuple[int, str, int] | None:
    """Read the three InventoryItem usr columns. None when hosted (no sqlcmd)."""
    if not instance().ssh:
        return None
    rows = sql_lines(
        "SELECT CAST(UsrQMSInspectionRequired AS int), "
        "RTRIM(ISNULL(UsrQMSInspectionPlanID, N'')), "
        "ISNULL(UsrMinShelfLifeDays, -1) "
        f"FROM {DB_NAME}.dbo.InventoryItem "
        f"WHERE CompanyID = {company_id()} "
        f"AND RTRIM(InventoryCD) = N'{inventory_cd}'"
    )
    if not rows:
        raise AssertionError(f"InventoryItem {inventory_cd} missing")
    required, plan, days = rows[0].split("|")
    return int(required), plan, int(days)


class TestStockItemPutV13(unittest.TestCase):
    """V13: PUT StockItem usr fields; GET roundtrip; GitOps six-item shape."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            reason = _seed_ready(session)
            if reason:
                raise unittest.SkipTest(reason)
            ensure_numbering_and_role(session)
            for rec in GITOPS_STOCK_ITEMS:
                item = session.get_record("StockItem", [rec["InventoryID"]])
                if item is None:
                    raise unittest.SkipTest(
                        f"StockItem {rec['InventoryID']} missing — "
                        "seed tenant from acu-gitops-qms"
                    )
            for plan in GITOPS_PLANS:
                qms_put(session, "InspectionPlan", plan)

    def test_stock_item_entity_lists(self) -> None:
        with client() as session:
            rows = qms_get(session, "StockItem", params={"$top": "1"})
        self.assertIsInstance(rows, list)

    def test_put_parts_item_persists_and_get_roundtrip(self) -> None:
        rec = dict(GITOPS_STOCK_ITEMS[0])
        self.assertEqual(rec["InventoryID"], ITEM_CD)
        rec["UsrMinShelfLifeDays"] = 181
        with client() as session:
            qms_put(session, "StockItem", rec)
            got = unwrap(qms_get(session, "StockItem", [ITEM_CD]))
        self._assert_usr_fields(got, rec)
        self._assert_sql_usr(rec)

    def test_gitops_six_item_put_shape_no_sql(self) -> None:
        self.assertEqual(len(GITOPS_STOCK_ITEMS), 6)
        with client() as session:
            for rec in GITOPS_STOCK_ITEMS:
                qms_put(session, "StockItem", rec)
                got = unwrap(qms_get(session, "StockItem", [rec["InventoryID"]]))
                self._assert_usr_fields(got, rec)
                self._assert_sql_usr(rec)

    def _assert_usr_fields(self, got: dict, rec: dict) -> None:
        cd = rec["InventoryID"]
        self.assertEqual((got.get("InventoryID") or "").strip(), cd, cd)
        self.assertEqual(
            bool(got.get("UsrQMSInspectionRequired")),
            rec["UsrQMSInspectionRequired"],
            cd,
        )
        self.assertEqual(
            (got.get("UsrQMSInspectionPlanID") or "").strip(),
            rec["UsrQMSInspectionPlanID"],
            cd,
        )
        self.assertEqual(
            int(got.get("UsrMinShelfLifeDays") or 0),
            rec["UsrMinShelfLifeDays"],
            cd,
        )
        for name in USR_ITEM_COLUMNS:
            self.assertIn(name, got, cd)

    def _assert_sql_usr(self, rec: dict) -> None:
        row = _sql_usr(rec["InventoryID"])
        if row is None:
            return
        required, plan, days = row
        cd = rec["InventoryID"]
        self.assertEqual(required, int(bool(rec["UsrQMSInspectionRequired"])), cd)
        self.assertEqual(plan.strip(), rec["UsrQMSInspectionPlanID"], cd)
        self.assertEqual(days, rec["UsrMinShelfLifeDays"], cd)


if __name__ == "__main__":
    unittest.main()
