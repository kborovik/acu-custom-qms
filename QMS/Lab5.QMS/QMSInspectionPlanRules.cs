namespace Lab5.QMS
{
    /// <summary>V7 plan-bounds: MinValue/MaxValue ordering and PlanID uppercase.</summary>
    public static class QMSInspectionPlanRules
    {
        public static bool BoundsValid(decimal? minValue, decimal? maxValue)
        {
            if (minValue == null || maxValue == null)
            {
                return true;
            }
            return minValue.Value <= maxValue.Value;
        }

        public static string NormalizePlanID(string planID)
        {
            return planID == null ? null : planID.ToUpperInvariant();
        }
    }
}
