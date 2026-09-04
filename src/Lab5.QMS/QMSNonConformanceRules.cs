namespace Lab5.QMS
{
    /// <summary>V6 fail-path NCR: CloseNCR root-cause gate and seed from a failed inspection order.</summary>
    public static class QMSNonConformanceRules
    {
        public const string AutomatedOosDescription =
            "Automated OOS Failure: Laboratory results breached acceptable tolerances.";

        public const string QuarantineRtvAction = "Quarantine Segregation & RTV Claim";

        public static bool CanClose(string rootCauseCategory)
        {
            return !string.IsNullOrWhiteSpace(rootCauseCategory);
        }

        public static void SeedFromFailedOrder(
            QMSNonConformance ncr,
            string inspectionOrderNbr,
            int? inventoryID,
            string lotSerialNbr,
            int? vendorID,
            string receiptNbr)
        {
            ncr.InspectionOrderNbr = inspectionOrderNbr;
            ncr.InventoryID = inventoryID;
            ncr.LotSerialNbr = lotSerialNbr;
            ncr.VendorID = vendorID;
            ncr.ReceiptNbr = receiptNbr;
            ncr.Status = QMSNonConformanceStatus.Open;
            ncr.Severity = QMSSeverity.Critical;
            ncr.Description = AutomatedOosDescription;
            ncr.ActionRequired = QuarantineRtvAction;
            ncr.InventoryHoldStatus = QMSInventoryHoldStatus.Quarantine;
        }
    }
}
