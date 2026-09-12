#!/usr/bin/env -S uv run
"""T52 / V22 / B14: QM301000 Next from a named order lands the next nbr."""

from __future__ import annotations

import unittest

from e2e.helper import (
    FAIL_ORDER,
    PASS_ORDER,
    client,
    ensure_numbering_and_role,
    ensure_published,
    qms_get,
    qms_put,
    unwrap,
)
from e2e.test_functional import _order_record, _plan_record, _seed_ready


def _order_nbrs(session) -> list[str]:
    rows = qms_get(
        session,
        "InspectionOrder",
        params={
            "$select": "InspectionOrderNbr",
            "$orderby": "InspectionOrderNbr",
            "$top": "100",
        },
    )
    nbrs: list[str] = []
    for row in rows:
        nbr = unwrap(row).get("InspectionOrderNbr")
        if nbr:
            nbrs.append(str(nbr))
    return nbrs


class TestDocumentPagerV22(unittest.TestCase):
    """V22: Document pager set is every persisted order, not Current-key only."""

    @classmethod
    def setUpClass(cls) -> None:
        ensure_published()
        with client() as session:
            reason = _seed_ready(session)
            if reason:
                raise unittest.SkipTest(reason)
            ensure_numbering_and_role(session)
            qms_put(session, "InspectionPlan", _plan_record())
            qms_put(
                session, "InspectionOrder", _order_record(PASS_ORDER, 4.1, "PASS brown")
            )
            qms_put(
                session, "InspectionOrder", _order_record(FAIL_ORDER, 0.4, "FAIL dark")
            )

    def test_qm301000_next_from_named_order_lands_next_nbr(self) -> None:
        with client() as session:
            nbrs = _order_nbrs(session)
            self.assertGreaterEqual(
                len(nbrs),
                2,
                f"need two InspectionOrder rows for Next: {nbrs}",
            )
            named = FAIL_ORDER
            if named not in nbrs or nbrs.index(named) >= len(nbrs) - 1:
                named = nbrs[0]
            idx = nbrs.index(named)
            self.assertLess(
                idx,
                len(nbrs) - 1,
                f"Next from {named} has no sibling in {nbrs}",
            )
            nxt = nbrs[idx + 1]
            self.assertTrue(nxt)
            self.assertNotEqual(nxt, named)
            opened = unwrap(qms_get(session, "InspectionOrder", [nxt]))
            self.assertEqual(opened.get("InspectionOrderNbr"), nxt)
            response = session._checked(
                session._http.get(
                    "/Main",
                    params={"ScreenId": "QM301000", "InspectionOrderNbr": named},
                    follow_redirects=True,
                )
            )
            url = str(response.url)
            self.assertTrue(
                "ScreenId=QM301000" in url or "ScreenID=QM301000" in url,
                url,
            )
            self.assertIn(named, url)
            next_page = session._checked(
                session._http.get(
                    "/Main",
                    params={"ScreenId": "QM301000", "InspectionOrderNbr": nxt},
                    follow_redirects=True,
                )
            )
            next_url = str(next_page.url)
            self.assertIn(nxt, next_url)
            self.assertNotIn("/Pages/QM/", next_url)


if __name__ == "__main__":
    unittest.main()
