using System;

namespace Lab5.QMS
{
    /// <summary>V4 evaluate: numeric bounds, text token, shelf-life, missing required, overall rollup.</summary>
    public static class QMSInspectionOrderRules
    {
        public static bool IsNumericTest(decimal? minValue, decimal? maxValue)
        {
            return minValue != null || maxValue != null;
        }

        public static string EvaluateNumeric(decimal? actual, decimal? minValue, decimal? maxValue, bool required)
        {
            if (actual == null)
            {
                return required ? QMSLineEvaluation.Fail : QMSLineEvaluation.Skipped;
            }
            if (minValue != null && actual.Value < minValue.Value)
            {
                return QMSLineEvaluation.Fail;
            }
            if (maxValue != null && actual.Value > maxValue.Value)
            {
                return QMSLineEvaluation.Fail;
            }
            return QMSLineEvaluation.Pass;
        }

        public static string EvaluateText(string actualText, string requiredToken, bool required)
        {
            if (string.IsNullOrWhiteSpace(actualText))
            {
                return required ? QMSLineEvaluation.Fail : QMSLineEvaluation.Skipped;
            }
            if (string.IsNullOrWhiteSpace(requiredToken))
            {
                return QMSLineEvaluation.Pass;
            }
            return actualText.IndexOf(requiredToken, StringComparison.OrdinalIgnoreCase) >= 0
                ? QMSLineEvaluation.Pass
                : QMSLineEvaluation.Fail;
        }

        public static string EvaluateLine(
            decimal? minValue,
            decimal? maxValue,
            decimal? actualNumeric,
            string actualText,
            string requiredToken,
            bool required)
        {
            if (IsNumericTest(minValue, maxValue))
            {
                return EvaluateNumeric(actualNumeric, minValue, maxValue, required);
            }
            return EvaluateText(actualText, requiredToken, required);
        }

        public static bool ShelfLifePass(DateTime? expiryDate, DateTime? receiptDate, int? minShelfLifeDays)
        {
            int days = minShelfLifeDays ?? 0;
            if (days <= 0)
            {
                return true;
            }
            if (expiryDate == null || receiptDate == null)
            {
                return false;
            }
            return expiryDate.Value.Date >= receiptDate.Value.Date.AddDays(days);
        }

        public static string Rollup(bool anyFail, bool anyMissingRequired, bool shelfLifePass)
        {
            if (anyFail || anyMissingRequired || !shelfLifePass)
            {
                return QMSOverallEvaluation.Fail;
            }
            return QMSOverallEvaluation.Pass;
        }
    }
}
