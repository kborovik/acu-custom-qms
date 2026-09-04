using System;
using System.Collections;
using PX.Data;
using PX.Objects.IN;
using PX.Objects.PO;

namespace Lab5.QMS
{
    public class QMSInspectionOrderEntry : PXGraph<QMSInspectionOrderEntry, QMSInspectionOrder>
    {
        public PXSelect<QMSInspectionOrder,
            Where<QMSInspectionOrder.inspectionOrderNbr, Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>>> Document;

        public PXSelect<QMSInspectionOrderResult,
            Where<QMSInspectionOrderResult.inspectionOrderNbr, Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>>> Results;

        public PXAction<QMSInspectionOrder> EvaluateResults;

        [PXButton(CommitChanges = true)]
        [PXUIField(DisplayName = "Evaluate")]
        protected virtual IEnumerable evaluateResults(PXAdapter adapter)
        {
            QMSInspectionOrder order = Document.Current;
            if (order == null)
            {
                return adapter.Get();
            }

            bool anyFail = false;
            bool anyMissingRequired = false;

            foreach (QMSInspectionPlanTest test in PXSelect<QMSInspectionPlanTest,
                Where<QMSInspectionPlanTest.planID, Equal<Required<QMSInspectionPlanTest.planID>>>>
                .Select(this, order.PlanID))
            {
                bool required = test.IsRequired ?? true;
                QMSInspectionOrderResult result = FindResult(test.LineNbr);
                if (result == null)
                {
                    if (required)
                    {
                        anyMissingRequired = true;
                    }
                    continue;
                }

                string evaluation = QMSInspectionOrderRules.EvaluateLine(
                    test.MinValue,
                    test.MaxValue,
                    result.ActualNumericValue,
                    result.ActualTextValue,
                    result.TargetSpec,
                    required);
                result.Evaluation = evaluation;
                Results.Update(result);
                if (evaluation == QMSLineEvaluation.Fail)
                {
                    anyFail = true;
                }
            }

            bool shelfLifePass = QMSInspectionOrderRules.ShelfLifePass(
                FindLotExpireDate(order),
                FindReceiptDate(order),
                FindMinShelfLifeDays(order));

            order.OverallEvaluation = QMSInspectionOrderRules.Rollup(anyFail, anyMissingRequired, shelfLifePass);
            order.EvaluatedByID = Accessinfo.UserID;
            order.EvaluationDateTime = DateTime.UtcNow;
            Document.Update(order);
            return adapter.Get();
        }

        protected virtual QMSInspectionOrderResult FindResult(int? lineNbr)
        {
            if (lineNbr == null)
            {
                return null;
            }
            foreach (QMSInspectionOrderResult row in Results.Select())
            {
                if (row.LineNbr != null && row.LineNbr.Value == lineNbr.Value)
                {
                    return row;
                }
            }
            return null;
        }

        protected virtual int? FindMinShelfLifeDays(QMSInspectionOrder order)
        {
            if (order.InventoryID == null)
            {
                return null;
            }
            InventoryItem item = PXSelect<InventoryItem,
                Where<InventoryItem.inventoryID, Equal<Required<InventoryItem.inventoryID>>>>
                .Select(this, order.InventoryID);
            if (item == null)
            {
                return null;
            }
            InventoryItemExt ext = item.GetExtension<InventoryItemExt>();
            return ext == null ? null : ext.UsrMinShelfLifeDays;
        }

        protected virtual DateTime? FindReceiptDate(QMSInspectionOrder order)
        {
            if (string.IsNullOrEmpty(order.ReceiptNbr))
            {
                return null;
            }
            POReceipt receipt = PXSelect<POReceipt,
                Where<POReceipt.receiptNbr, Equal<Required<POReceipt.receiptNbr>>>>
                .Select(this, order.ReceiptNbr);
            return receipt == null ? (DateTime?)null : receipt.ReceiptDate;
        }

        protected virtual DateTime? FindLotExpireDate(QMSInspectionOrder order)
        {
            if (order.InventoryID == null || string.IsNullOrEmpty(order.LotSerialNbr))
            {
                return null;
            }
            INLotSerialStatus lot = PXSelect<INLotSerialStatus,
                Where<INLotSerialStatus.inventoryID, Equal<Required<INLotSerialStatus.inventoryID>>,
                    And<INLotSerialStatus.lotSerialNbr, Equal<Required<INLotSerialStatus.lotSerialNbr>>>>>
                .Select(this, order.InventoryID, order.LotSerialNbr);
            return lot == null ? (DateTime?)null : lot.ExpireDate;
        }
    }
}
