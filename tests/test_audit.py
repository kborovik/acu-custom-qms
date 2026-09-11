#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
"""T10 / V3 / I.role: audit stamps + QC Hold to Released gate."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
PLAN_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionPlan.cs"
ORDER_CS = ROOT / "QMS" / "Lab5.QMS" / "DAC" / "QMSInspectionOrder.cs"
GRAPH_CS = ROOT / "QMS" / "Lab5.QMS" / "Graph" / "QMSInspectionOrderEntry.cs"
RULES_CS = ROOT / "QMS" / "Lab5.QMS" / "QMSAuditRules.cs"
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
SQL = ROOT / "QMS" / "SQL" / "CreateQMSTables.sql"

QUALITY_MANAGER = "Quality Manager"
INGESTION_ACCOUNT = "qms-ingestion"
RELEASED = "Released"
QUARANTINE = "Quarantine"
QC_HOLD = "QC Hold"

AUDIT_FIELDS = (
    "CreatedByID",
    "CreatedDateTime",
    "LastModifiedByID",
    "LastModifiedDateTime",
)

AUDIT_ATTRIBUTES = (
    "[PXDBCreatedByID]",
    "[PXDBCreatedDateTime]",
    "[PXDBLastModifiedByID]",
    "[PXDBLastModifiedDateTime]",
)


def stamp_evaluated_by_id(existing: UUID | None, user_id: UUID | None) -> UUID | None:
    return existing if existing is not None else user_id


def stamp_evaluation_datetime(
    existing: datetime | None, now: datetime
) -> datetime | None:
    return existing if existing is not None else now


def has_quality_manager_role(roles: list[str] | None) -> bool:
    if roles is None:
        return False
    return any(role.lower() == QUALITY_MANAGER.lower() for role in roles)


def is_ingestion_service_account(user_name: str | None) -> bool:
    if not user_name:
        return False
    return user_name.lower() == INGESTION_ACCOUNT.lower()


def may_release_lot(
    target_lot_status: str | None,
    has_qm: bool,
    is_ingestion: bool,
) -> bool:
    if target_lot_status != RELEASED:
        return True
    return has_qm or is_ingestion


def _table_block(sql: str, table: str) -> str:
    marker = f"CREATE TABLE [dbo].[{table}]"
    start = sql.index(marker)
    end = sql.find("CREATE TABLE", start + 1)
    return sql[start:] if end < 0 else sql[start:end]


class TestAuditFieldsV3(unittest.TestCase):
    def test_plan_and_order_carry_audit_attributes(self) -> None:
        plan = PLAN_CS.read_text(encoding="utf-8")
        order = ORDER_CS.read_text(encoding="utf-8")
        for name in AUDIT_FIELDS:
            self.assertIn(f"#region {name}", plan)
            self.assertIn(f"#region {name}", order)
        for attr in AUDIT_ATTRIBUTES:
            self.assertIn(attr, plan)
            self.assertIn(attr, order)

    def test_sql_plan_and_order_audit_columns(self) -> None:
        sql = SQL.read_text(encoding="utf-8")
        for table in ("UsrQMSInspectionPlan", "UsrQMSInspectionOrder"):
            block = _table_block(sql, table)
            self.assertIn("[CreatedByID] [uniqueidentifier] NOT NULL", block)
            self.assertIn("[CreatedDateTime] [datetime] NOT NULL", block)
            self.assertIn("[LastModifiedByID] [uniqueidentifier] NOT NULL", block)
            self.assertIn("[LastModifiedDateTime] [datetime] NOT NULL", block)

    def test_order_evaluation_stamp_columns(self) -> None:
        order = ORDER_CS.read_text(encoding="utf-8")
        self.assertIn("#region EvaluatedByID", order)
        self.assertIn("#region EvaluationDateTime", order)
        self.assertIn("[PXDBGuid]", order)
        self.assertIn(
            "[PXSelector(typeof(Search<Users.pKID>), SubstituteKey = typeof(Users.username))]",
            order,
        )
        self.assertIn("[PXDBDateAndTime]", order)
        sql = _table_block(SQL.read_text(encoding="utf-8"), "UsrQMSInspectionOrder")
        self.assertIn("[EvaluatedByID] [uniqueidentifier] NULL", sql)
        self.assertIn("[EvaluationDateTime] [datetime] NULL", sql)


class TestPermanentEvaluationStampV3(unittest.TestCase):
    def test_first_evaluate_stamps_user_and_time(self) -> None:
        user = uuid4()
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(stamp_evaluated_by_id(None, user), user)
        self.assertEqual(stamp_evaluation_datetime(None, now), now)

    def test_reevaluate_keeps_original_stamp(self) -> None:
        original_user = uuid4()
        later_user = uuid4()
        first = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        later = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(
            stamp_evaluated_by_id(original_user, later_user), original_user
        )
        self.assertEqual(stamp_evaluation_datetime(first, later), first)

    def test_csharp_stamp_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            "public static Guid? StampEvaluatedByID(Guid? existing, Guid? userId)",
            src,
        )
        self.assertIn("return existing ?? userId;", src)
        self.assertIn(
            "public static DateTime? StampEvaluationDateTime(DateTime? existing, DateTime now)",
            src,
        )
        self.assertIn("return existing ?? now;", src)
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn(
            "order.EvaluatedByID = QMSAuditRules.StampEvaluatedByID(order.EvaluatedByID, Accessinfo.UserID);",
            graph,
        )
        self.assertIn(
            "order.EvaluationDateTime = QMSAuditRules.StampEvaluationDateTime(order.EvaluationDateTime, DateTime.UtcNow);",
            graph,
        )
        html = HTML.read_text(encoding="utf-8")
        self.assertIn('name="EvaluatedByID"', html)
        self.assertIn('name="EvaluationDateTime"', html)


class TestReleaseGateIRoleV3(unittest.TestCase):
    def test_quality_manager_may_release(self) -> None:
        self.assertTrue(has_quality_manager_role([QUALITY_MANAGER]))
        self.assertTrue(has_quality_manager_role(["quality manager"]))
        self.assertTrue(
            may_release_lot(
                RELEASED, has_quality_manager_role([QUALITY_MANAGER]), False
            )
        )

    def test_ingestion_service_account_may_release(self) -> None:
        self.assertTrue(is_ingestion_service_account(INGESTION_ACCOUNT))
        self.assertTrue(is_ingestion_service_account("QMS-INGESTION"))
        self.assertTrue(
            may_release_lot(
                RELEASED, False, is_ingestion_service_account(INGESTION_ACCOUNT)
            )
        )

    def test_unprivileged_blocked_from_released(self) -> None:
        self.assertFalse(has_quality_manager_role(["Administrator"]))
        self.assertFalse(has_quality_manager_role(None))
        self.assertFalse(is_ingestion_service_account("admin"))
        self.assertFalse(is_ingestion_service_account(None))
        self.assertFalse(may_release_lot(RELEASED, False, False))

    def test_quarantine_and_hold_skip_gate(self) -> None:
        self.assertTrue(may_release_lot(QUARANTINE, False, False))
        self.assertTrue(may_release_lot(QC_HOLD, False, False))

    def test_csharp_gate_match_oracle(self) -> None:
        src = RULES_CS.read_text(encoding="utf-8")
        self.assertIn(
            f'public const string QualityManagerRole = "{QUALITY_MANAGER}"', src
        )
        self.assertIn(
            f'public const string IngestionServiceAccount = "{INGESTION_ACCOUNT}"',
            src,
        )
        self.assertIn(
            "public static bool HasQualityManagerRole(IEnumerable<string> roles)",
            src,
        )
        self.assertIn(
            "string.Equals(role, QualityManagerRole, StringComparison.OrdinalIgnoreCase)",
            src,
        )
        self.assertIn(
            "public static bool IsIngestionServiceAccount(string userName)",
            src,
        )
        self.assertIn(
            "string.Equals(userName, IngestionServiceAccount, StringComparison.OrdinalIgnoreCase)",
            src,
        )
        self.assertIn(
            "public static bool MayReleaseLot(",
            src,
        )
        self.assertIn("if (targetLotStatus != QMSLotStatus.Released)", src)
        self.assertIn("return hasQualityManagerRole || isIngestionServiceAccount;", src)
        graph = GRAPH_CS.read_text(encoding="utf-8")
        self.assertIn("QMSAuditRules.MayReleaseLot(", graph)
        self.assertIn(
            "QMSAuditRules.HasQualityManagerRole(QMSAccess.CurrentUserRoles())", graph
        )
        self.assertIn(
            "QMSAuditRules.IsIngestionServiceAccount(QMSAccess.CurrentUserName())",
            graph,
        )
        access = (ROOT / "QMS" / "Lab5.QMS" / "QMSAccess.cs").read_text(
            encoding="utf-8"
        )
        self.assertIn("PXAccess.GetRoles(PXAccess.GetUserName())", access)
        self.assertIn("list.Common", access)
        self.assertIn("PXSelect<UsersInRoles", access)
        self.assertIn(
            "QC Hold to Released requires Quality Manager role or the ingestion service account.",
            graph,
        )


if __name__ == "__main__":
    unittest.main()
