using System.Collections;
using PX.Data;
using PX.Objects.IN;
using PX.Objects.PO;

namespace Lab5.QMS
{
    public class POReceiptEntry_Extension : PXGraphExtension<POReceiptEntry>
    {
        public static bool IsActive()
        {
            return true;
        }

        public delegate IEnumerable ReleaseDelegate(PXAdapter adapter);

        [PXOverride]
        public IEnumerable Release(PXAdapter adapter, ReleaseDelegate baseMethod)
        {
            IEnumerable result = baseMethod(adapter);
            POReceipt doc = Base.Document.Current;
            if (doc != null)
            {
                ApplyInspectionGate(doc);
            }
            return result;
        }

        protected virtual void ApplyInspectionGate(POReceipt doc)
        {
            foreach (POReceiptLine line in PXSelect<POReceiptLine,
                Where<POReceiptLine.receiptNbr, Equal<Required<POReceiptLine.receiptNbr>>>>
                .Select(Base, doc.ReceiptNbr))
            {
                InventoryItem item = PXSelect<InventoryItem,
                    Where<InventoryItem.inventoryID, Equal<Required<InventoryItem.inventoryID>>>>
                    .Select(Base, line.InventoryID);
                if (item == null)
                {
                    continue;
                }
                InventoryItemExt itemExt = item.GetExtension<InventoryItemExt>();
                if (!QMSReceiptReleaseRules.RequiresInspection(itemExt?.UsrQMSInspectionRequired))
                {
                    continue;
                }

                foreach (POReceiptLineSplit split in PXSelect<POReceiptLineSplit,
                    Where<POReceiptLineSplit.receiptNbr, Equal<Required<POReceiptLineSplit.receiptNbr>>,
                        And<POReceiptLineSplit.lineNbr, Equal<Required<POReceiptLineSplit.lineNbr>>>>>
                    .Select(Base, line.ReceiptNbr, line.LineNbr))
                {
                    if (!QMSReceiptReleaseRules.HasLot(split.LotSerialNbr))
                    {
                        continue;
                    }
                    UpdateLotStatus(item.InventoryID, split.LotSerialNbr, QMSLotStatus.QcHold);
                    CreateDraftInspectionOrder(doc, line, split, itemExt.UsrQMSInspectionPlanID);
                }
            }
        }

        protected virtual void UpdateLotStatus(int? inventoryID, string lotSerialNbr, string lotStatus)
        {
            QMSLotIssueGate.WriteLotStatus(Base, inventoryID, lotSerialNbr, lotStatus);
        }

        protected virtual void CreateDraftInspectionOrder(
            POReceipt doc,
            POReceiptLine line,
            POReceiptLineSplit split,
            string planID)
        {
            QMSInspectionOrder existing = PXSelect<QMSInspectionOrder,
                Where<QMSInspectionOrder.receiptNbr, Equal<Required<QMSInspectionOrder.receiptNbr>>,
                    And<QMSInspectionOrder.lotSerialNbr, Equal<Required<QMSInspectionOrder.lotSerialNbr>>>>>
                .Select(Base, doc.ReceiptNbr, split.LotSerialNbr);
            if (existing != null)
            {
                return;
            }

            QMSInspectionOrderEntry graph = PXGraph.CreateInstance<QMSInspectionOrderEntry>();
            QMSInspectionOrder order = new QMSInspectionOrder();
            QMSReceiptReleaseRules.SeedDraftOrder(
                order,
                QMSReceiptReleaseRules.DraftOrderNbr(doc.ReceiptNbr, split.LotSerialNbr),
                line.InventoryID,
                split.LotSerialNbr,
                doc.VendorID,
                doc.ReceiptNbr,
                planID);
            graph.Document.Insert(order);
            graph.Actions.PressSave();
        }
    }
}
