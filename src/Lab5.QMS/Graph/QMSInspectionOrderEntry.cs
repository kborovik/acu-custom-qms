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

        public PXSetup<QMSSetup> QMSSetup;

        protected virtual void QMSInspectionOrderResult_RowInserting(PXCache sender, PXRowInsertingEventArgs e)
        {
            QMSInspectionOrderResult row = e.Row as QMSInspectionOrderResult;
            if (row == null)
            {
                return;
            }
            if (row.LineNbr == null || row.LineNbr == 0)
            {
                int max = 0;
                foreach (QMSInspectionOrderResult result in Results.Select())
                {
                    if (result.LineNbr != null && result.LineNbr.Value > max)
                    {
                        max = result.LineNbr.Value;
                    }
                }
                row.LineNbr = max + 10;
                return;
            }
            QMSInspectionOrderResult existing = FindPersistedResult(row.LineNbr);
            if (existing == null || ReferenceEquals(existing, row))
            {
                return;
            }
            CopyPendingResultFields(sender, row, existing);
            Results.Update(existing);
            e.Cancel = true;
        }

        protected virtual void CopyPendingResultFields(
            PXCache sender, QMSInspectionOrderResult src, QMSInspectionOrderResult dst)
        {
            CopyPendingField<QMSInspectionOrderResult.testID>(sender, src, dst);
            CopyPendingField<QMSInspectionOrderResult.testMethod>(sender, src, dst);
            CopyPendingField<QMSInspectionOrderResult.targetSpec>(sender, src, dst);
            CopyPendingField<QMSInspectionOrderResult.actualNumericValue>(sender, src, dst);
            CopyPendingField<QMSInspectionOrderResult.actualTextValue>(sender, src, dst);
            CopyPendingField<QMSInspectionOrderResult.evaluation>(sender, src, dst);
            CopyPendingField<QMSInspectionOrderResult.notes>(sender, src, dst);
        }

        protected virtual void CopyPendingField<TField>(PXCache sender, object src, object dst)
            where TField : IBqlField
        {
            object pending = sender.GetValuePending<TField>(src);
            if (ReferenceEquals(pending, PXCache.NotSetValue))
            {
                return;
            }
            sender.SetValue<TField>(dst, sender.GetValue<TField>(src));
        }

        public PXAction<QMSInspectionOrder> EvaluateResults;
        public PXAction<QMSInspectionOrder> ReleaseLotDecision;

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
            order.EvaluatedByID = QMSAuditRules.StampEvaluatedByID(order.EvaluatedByID, Accessinfo.UserID);
            order.EvaluationDateTime = QMSAuditRules.StampEvaluationDateTime(order.EvaluationDateTime, DateTime.UtcNow);
            Document.Update(order);
            return adapter.Get();
        }

        [PXButton(CommitChanges = true)]
        [PXUIField(DisplayName = "Release Lot Decision")]
        protected virtual IEnumerable releaseLotDecision(PXAdapter adapter)
        {
            QMSInspectionOrder order = Document.Current;
            if (order == null)
            {
                return adapter.Get();
            }
            if (!QMSLotDecisionRules.CanRelease(order.OverallEvaluation, order.Status))
            {
                throw new PXException("Overall evaluation must be Pass or Fail on an open inspection order.");
            }

            string lotStatus = QMSLotDecisionRules.TargetLotStatus(order.OverallEvaluation);
            if (!QMSAuditRules.MayReleaseLot(
                lotStatus,
                QMSAuditRules.HasQualityManagerRole(QMSAccess.CurrentUserRoles()),
                QMSAuditRules.IsIngestionServiceAccount(QMSAccess.CurrentUserName())))
            {
                throw new PXException(
                    "QC Hold to Released requires Quality Manager role or the ingestion service account.");
            }
            UpdateLotStatus(order.InventoryID, order.LotSerialNbr, lotStatus);

            if (QMSLotDecisionRules.ShouldCreateNcr(order.OverallEvaluation))
            {
                CreateNcrFromFailedOrder(order);
            }

            order.Status = QMSInspectionOrderStatus.Completed;
            Document.Update(order);
            return adapter.Get();
        }

        protected virtual void UpdateLotStatus(int? inventoryID, string lotSerialNbr, string lotStatus)
        {
            if (inventoryID == null || !QMSReceiptReleaseRules.HasLot(lotSerialNbr))
            {
                return;
            }
            INLotSerialStatus lot = PXSelect<INLotSerialStatus,
                Where<INLotSerialStatus.inventoryID, Equal<Required<INLotSerialStatus.inventoryID>>,
                    And<INLotSerialStatus.lotSerialNbr, Equal<Required<INLotSerialStatus.lotSerialNbr>>>>>
                .Select(this, inventoryID, lotSerialNbr);
            if (lot == null)
            {
                return;
            }
            INLotSerialStatusExt ext = lot.GetExtension<INLotSerialStatusExt>();
            if (ext != null)
            {
                ext.UsrQMSLotStatus = lotStatus;
            }
            Caches[typeof(INLotSerialStatus)].Update(lot);
        }

        protected virtual void CreateNcrFromFailedOrder(QMSInspectionOrder order)
        {
            QMSNonConformance existing = PXSelect<QMSNonConformance,
                Where<QMSNonConformance.inspectionOrderNbr, Equal<Required<QMSNonConformance.inspectionOrderNbr>>>>
                .Select(this, order.InspectionOrderNbr);
            if (existing != null)
            {
                return;
            }

            QMSNonConformanceEntry graph = PXGraph.CreateInstance<QMSNonConformanceEntry>();
            QMSNonConformance ncr = new QMSNonConformance();
            ncr.NCRNbr = QMSLotDecisionRules.NcrNbr(order.InspectionOrderNbr);
            QMSNonConformanceRules.SeedFromFailedOrder(
                ncr,
                order.InspectionOrderNbr,
                order.InventoryID,
                order.LotSerialNbr,
                order.VendorID,
                order.ReceiptNbr);
            graph.Document.Insert(ncr);
            graph.Actions.PressSave();
        }

        protected virtual QMSInspectionOrderResult FindPersistedResult(int? lineNbr)
        {
            if (lineNbr == null)
            {
                return null;
            }
            foreach (QMSInspectionOrderResult row in Results.Select())
            {
                if (row.LineNbr != null
                    && row.LineNbr.Value == lineNbr.Value
                    && Results.Cache.GetStatus(row) != PXEntryStatus.Inserted)
                {
                    return row;
                }
            }
            return PXSelect<QMSInspectionOrderResult,
                Where<QMSInspectionOrderResult.inspectionOrderNbr, Equal<Current<QMSInspectionOrder.inspectionOrderNbr>>,
                    And<QMSInspectionOrderResult.lineNbr, Equal<Required<QMSInspectionOrderResult.lineNbr>>>>>
                .Select(this, lineNbr);
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
