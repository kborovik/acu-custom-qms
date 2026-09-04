using System;
using System.Text;

namespace Lab5.QMS
{
    /// <summary>V1/V9 dock release: QC Hold gate and draft inspection order from PO receipt lots.</summary>
    public static class QMSReceiptReleaseRules
    {
        public static bool RequiresInspection(bool? required)
        {
            return required == true;
        }

        public static bool HasLot(string lotSerialNbr)
        {
            return !string.IsNullOrWhiteSpace(lotSerialNbr);
        }

        public static bool ThreeWayLinkConsistent(
            string receiptNbr,
            string lotSerialNbr,
            string orderReceiptNbr,
            string orderLotSerialNbr)
        {
            return string.Equals(receiptNbr, orderReceiptNbr, StringComparison.Ordinal)
                && string.Equals(lotSerialNbr, orderLotSerialNbr, StringComparison.Ordinal);
        }

        public static string DraftOrderNbr(string receiptNbr, string lotSerialNbr)
        {
            return "Q" + CompactToken(receiptNbr, 7) + CompactToken(lotSerialNbr, 7);
        }

        public static void SeedDraftOrder(
            QMSInspectionOrder order,
            string inspectionOrderNbr,
            int? inventoryID,
            string lotSerialNbr,
            int? vendorID,
            string receiptNbr,
            string planID)
        {
            order.InspectionOrderNbr = inspectionOrderNbr;
            order.InventoryID = inventoryID;
            order.LotSerialNbr = lotSerialNbr;
            order.VendorID = vendorID;
            order.ReceiptNbr = receiptNbr;
            order.PlanID = planID;
            order.Status = QMSInspectionOrderStatus.Open;
            order.OverallEvaluation = QMSOverallEvaluation.Pending;
        }

        public static string CompactToken(string value, int width)
        {
            if (width <= 0)
            {
                return string.Empty;
            }
            if (string.IsNullOrEmpty(value))
            {
                return new string('0', width);
            }
            StringBuilder sb = new StringBuilder(value.Length);
            foreach (char c in value)
            {
                if (char.IsLetterOrDigit(c))
                {
                    sb.Append(char.ToUpperInvariant(c));
                }
            }
            string alnum = sb.ToString();
            if (alnum.Length == 0)
            {
                return new string('0', width);
            }
            if (alnum.Length <= width)
            {
                return alnum.PadLeft(width, '0');
            }
            return alnum.Substring(alnum.Length - width);
        }
    }
}
