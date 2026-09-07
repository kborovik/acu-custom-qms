using PX.Data;

namespace Lab5.QMS
{
    public class QMSInspectionPlanMaint : PXGraph<QMSInspectionPlanMaint, QMSInspectionPlan>
    {
        public PXSelect<QMSInspectionPlan,
            Where<QMSInspectionPlan.planID, Equal<Current<QMSInspectionPlan.planID>>>> Document;

        public PXSelect<QMSInspectionPlanTest,
            Where<QMSInspectionPlanTest.planID, Equal<Current<QMSInspectionPlan.planID>>>,
            OrderBy<Asc<QMSInspectionPlanTest.lineNbr>>> Tests;

        protected virtual void QMSInspectionPlan_PlanID_FieldUpdating(PXCache sender, PXFieldUpdatingEventArgs e)
        {
            if (e.NewValue is string planID)
            {
                e.NewValue = QMSInspectionPlanRules.NormalizePlanID(planID);
            }
        }

        protected virtual void QMSInspectionPlan_RowPersisting(PXCache sender, PXRowPersistingEventArgs e)
        {
            QMSInspectionPlan row = e.Row as QMSInspectionPlan;
            if (row?.PlanID != null)
            {
                row.PlanID = QMSInspectionPlanRules.NormalizePlanID(row.PlanID);
            }
        }

        protected virtual void QMSInspectionPlanTest_RowInserting(PXCache sender, PXRowInsertingEventArgs e)
        {
            QMSInspectionPlanTest row = e.Row as QMSInspectionPlanTest;
            if (row == null)
            {
                return;
            }
            if (row.LineNbr == null || row.LineNbr == 0)
            {
                int max = 0;
                foreach (QMSInspectionPlanTest test in Tests.Select())
                {
                    if (test.LineNbr != null && test.LineNbr.Value > max)
                    {
                        max = test.LineNbr.Value;
                    }
                }
                row.LineNbr = max + 10;
                return;
            }
            QMSInspectionPlanTest existing = FindPersistedTest(row.LineNbr);
            if (existing == null || ReferenceEquals(existing, row))
            {
                return;
            }
            existing.TestID = row.TestID;
            existing.Description = row.Description;
            existing.TestMethod = row.TestMethod;
            existing.TargetValue = row.TargetValue;
            existing.MinValue = row.MinValue;
            existing.MaxValue = row.MaxValue;
            existing.UOM = row.UOM;
            existing.Criticality = row.Criticality;
            Tests.Update(existing);
            e.Cancel = true;
        }

        protected virtual QMSInspectionPlanTest FindPersistedTest(int? lineNbr)
        {
            if (lineNbr == null)
            {
                return null;
            }
            foreach (QMSInspectionPlanTest test in Tests.Select())
            {
                if (test.LineNbr != null
                    && test.LineNbr.Value == lineNbr.Value
                    && Tests.Cache.GetStatus(test) != PXEntryStatus.Inserted)
                {
                    return test;
                }
            }
            return PXSelect<QMSInspectionPlanTest,
                Where<QMSInspectionPlanTest.planID, Equal<Current<QMSInspectionPlan.planID>>,
                    And<QMSInspectionPlanTest.lineNbr, Equal<Required<QMSInspectionPlanTest.lineNbr>>>>>
                .Select(this, lineNbr);
        }

        protected virtual void QMSInspectionPlanTest_RowPersisting(PXCache sender, PXRowPersistingEventArgs e)
        {
            QMSInspectionPlanTest row = e.Row as QMSInspectionPlanTest;
            if (row == null)
            {
                return;
            }
            if (!QMSInspectionPlanRules.BoundsValid(row.MinValue, row.MaxValue))
            {
                sender.RaiseExceptionHandling<QMSInspectionPlanTest.minValue>(
                    row,
                    row.MinValue,
                    new PXSetPropertyException("MinValue must be less than or equal to MaxValue."));
                throw new PXRowPersistingException(
                    typeof(QMSInspectionPlanTest.minValue).Name,
                    row.MinValue,
                    "MinValue must be less than or equal to MaxValue.");
            }
        }
    }
}
