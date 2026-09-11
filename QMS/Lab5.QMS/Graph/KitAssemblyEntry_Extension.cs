using System.Collections;
using PX.Data;
using PX.Objects.IN;

namespace Lab5.QMS
{
    /// <summary>IN307000 Kit Assembly: refuse QC Hold / Quarantine component lots on allocate/issue.</summary>
    public class KitAssemblyEntry_Extension : PXGraphExtension<KitAssemblyEntry>
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

        protected virtual void INComponentTran_LotSerialNbr_FieldVerifying(
            PXCache sender, PXFieldVerifyingEventArgs e)
        {
            INComponentTran line = e.Row as INComponentTran;
            QMSLotIssueGate.ThrowIfNotIssuable(
                sender.Graph, line == null ? null : line.InventoryID, e.NewValue as string, true);
        }

        protected virtual void INComponentTranSplit_LotSerialNbr_FieldVerifying(
            PXCache sender, PXFieldVerifyingEventArgs e)
        {
            INComponentTranSplit split = e.Row as INComponentTranSplit;
            QMSLotIssueGate.ThrowIfNotIssuable(
                sender.Graph, split == null ? null : split.InventoryID, e.NewValue as string, true);
        }

        protected virtual void INComponentTran_RowPersisting(PXCache sender, PXRowPersistingEventArgs e)
        {
            if ((e.Operation & PXDBOperation.Command) == PXDBOperation.Delete)
            {
                return;
            }
            INComponentTran line = e.Row as INComponentTran;
            if (line == null)
            {
                return;
            }
            QMSLotIssueGate.ThrowIfNotIssuable(sender.Graph, line.InventoryID, line.LotSerialNbr);
        }

        protected virtual void INComponentTranSplit_RowPersisting(
            PXCache sender, PXRowPersistingEventArgs e)
        {
            if ((e.Operation & PXDBOperation.Command) == PXDBOperation.Delete)
            {
                return;
            }
            INComponentTranSplit split = e.Row as INComponentTranSplit;
            if (split == null)
            {
                return;
            }
            QMSLotIssueGate.ThrowIfNotIssuable(sender.Graph, split.InventoryID, split.LotSerialNbr);
        }

        protected virtual void AssertLots()
        {
            INKitRegister doc = Base.Document.Current;
            QMSLotIssueGate.AssertKitLots(
                Base, doc == null ? null : doc.DocType, doc == null ? null : doc.RefNbr);
        }
    }
}
