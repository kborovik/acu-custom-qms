namespace Lab5.QMS
{
    /// <summary>V5/V6/V9 lot decision: pass Released, fail Quarantine + NCR, halt allocation.</summary>
    public static class QMSLotDecisionRules
    {
        public static bool CanRelease(string overallEvaluation, string orderStatus)
        {
            if (orderStatus == QMSInspectionOrderStatus.Completed
                || orderStatus == QMSInspectionOrderStatus.Cancelled)
            {
                return false;
            }
            return overallEvaluation == QMSOverallEvaluation.Pass
                || overallEvaluation == QMSOverallEvaluation.Fail;
        }

        public static string TargetLotStatus(string overallEvaluation)
        {
            if (overallEvaluation == QMSOverallEvaluation.Pass)
            {
                return QMSLotStatus.Released;
            }
            if (overallEvaluation == QMSOverallEvaluation.Fail)
            {
                return QMSLotStatus.Quarantine;
            }
            return QMSLotStatus.QcHold;
        }

        public static bool ShouldCreateNcr(string overallEvaluation)
        {
            return overallEvaluation == QMSOverallEvaluation.Fail;
        }

        public static bool IsAllocatable(string lotStatus)
        {
            return lotStatus == QMSLotStatus.Released;
        }

        public static string NcrNbr(string inspectionOrderNbr)
        {
            return "N" + QMSReceiptReleaseRules.CompactToken(inspectionOrderNbr, 14);
        }
    }
}
