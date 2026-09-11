using System.Collections;
using PX.Data;
using PX.Objects.IN;

namespace Lab5.QMS
{
    /// <summary>IN302000 Issues: refuse QC Hold / Quarantine lots on allocate/issue.</summary>
    public class INIssueEntry_Extension : PXGraphExtension<INIssueEntry>
    {
        public static bool IsActive()
        {
            return true;
        }

        public delegate IEnumerable ReleaseDelegate(PXAdapter adapter);

        [PXOverride]
        public IEnumerable Release(PXAdapter adapter, ReleaseDelegate baseMethod)
        {
            AssertLots();
            return baseMethod(adapter);
        }

        public delegate void PersistDelegate();

        [PXOverride]
        public void Persist(PersistDelegate baseMethod)
        {
            AssertLots();
            baseMethod();
        }

        protected virtual void INTran_LotSerialNbr_FieldVerifying(
            PXCache sender, PXFieldVerifyingEventArgs e)
        {
            INTran line = e.Row as INTran;
            QMSLotIssueGate.ThrowIfNotIssuable(
                sender.Graph, line == null ? null : line.InventoryID, e.NewValue as string, true);
        }

        protected virtual void INTranSplit_LotSerialNbr_FieldVerifying(
            PXCache sender, PXFieldVerifyingEventArgs e)
        {
            INTranSplit split = e.Row as INTranSplit;
            QMSLotIssueGate.ThrowIfNotIssuable(
                sender.Graph, split == null ? null : split.InventoryID, e.NewValue as string, true);
        }

        protected virtual void INTran_RowPersisting(PXCache sender, PXRowPersistingEventArgs e)
        {
            if ((e.Operation & PXDBOperation.Command) == PXDBOperation.Delete)
            {
                return;
            }
            INTran line = e.Row as INTran;
            if (line == null)
            {
                return;
            }
            QMSLotIssueGate.ThrowIfNotIssuable(sender.Graph, line.InventoryID, line.LotSerialNbr);
        }

        protected virtual void INTranSplit_RowPersisting(PXCache sender, PXRowPersistingEventArgs e)
        {
            if ((e.Operation & PXDBOperation.Command) == PXDBOperation.Delete)
            {
                return;
            }
            INTranSplit split = e.Row as INTranSplit;
            if (split == null)
            {
                return;
            }
            QMSLotIssueGate.ThrowIfNotIssuable(sender.Graph, split.InventoryID, split.LotSerialNbr);
        }

        protected virtual void AssertLots()
        {
            INRegister doc = Base.issue.Current;
            QMSLotIssueGate.AssertIssueLots(
                Base, doc == null ? null : doc.DocType, doc == null ? null : doc.RefNbr);
        }
    }
}
