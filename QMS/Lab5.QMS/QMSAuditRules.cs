using System;
using System.Collections.Generic;

namespace Lab5.QMS
{
    /// <summary>V3/I.role: GMP audit stamps + QC Hold to Released authorization.</summary>
    public static class QMSAuditRules
    {
        public const string QualityManagerRole = "Quality Manager";
        public const string IngestionServiceAccount = "qms-ingestion";

        public static Guid? StampEvaluatedByID(Guid? existing, Guid? userId)
        {
            return existing ?? userId;
        }

        public static DateTime? StampEvaluationDateTime(DateTime? existing, DateTime now)
        {
            return existing ?? now;
        }

        public static bool HasQualityManagerRole(IEnumerable<string> roles)
        {
            if (roles == null)
            {
                return false;
            }
            foreach (string role in roles)
            {
                if (string.Equals(role, QualityManagerRole, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
            return false;
        }

        public static bool IsIngestionServiceAccount(string userName)
        {
            if (string.IsNullOrEmpty(userName))
            {
                return false;
            }
            return string.Equals(userName, IngestionServiceAccount, StringComparison.OrdinalIgnoreCase);
        }

        public static bool MayReleaseLot(
            string targetLotStatus,
            bool hasQualityManagerRole,
            bool isIngestionServiceAccount)
        {
            if (targetLotStatus != QMSLotStatus.Released)
            {
                return true;
            }
            return hasQualityManagerRole || isIngestionServiceAccount;
        }
    }
}
