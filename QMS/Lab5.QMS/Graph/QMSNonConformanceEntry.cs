using System.Collections;
using PX.Data;
using PX.Objects.PO;

namespace Lab5.QMS
{
    public class QMSNonConformanceEntry : PXGraph<QMSNonConformanceEntry, QMSNonConformance>
    {
        public PXSelect<QMSNonConformance> Document;

        public PXSetup<QMSSetup> QMSSetup;

        public PXAction<QMSNonConformance> CloseNCR;

        [PXButton(CommitChanges = true)]
        [PXUIField(DisplayName = "CloseNCR")]
        protected virtual IEnumerable closeNCR(PXAdapter adapter)
        {
            QMSNonConformance ncr = Document.Current;
            if (ncr == null)
            {
                return adapter.Get();
            }
            if (!QMSNonConformanceRules.CanClose(ncr.RootCauseCategory))
            {
                throw new PXException("Root cause category is required before closing the NCR.");
            }
            ncr.Status = QMSNonConformanceStatus.Closed;
            Document.Update(ncr);
            return adapter.Get();
        }

        public PXAction<QMSNonConformance> DispositionRTV;

        [PXButton(CommitChanges = true)]
        [PXUIField(DisplayName = "DispositionRTV")]
        protected virtual IEnumerable dispositionRTV(PXAdapter adapter)
        {
            QMSNonConformance ncr = Document.Current;
            if (ncr == null)
            {
                return adapter.Get();
            }
            if (string.IsNullOrEmpty(ncr.ReceiptNbr))
            {
                throw new PXException("Receipt Nbr is required for Return to Vendor.");
            }

            POReceiptEntry graph = PXGraph.CreateInstance<POReceiptEntry>();
            graph.Document.Current = PXSelect<POReceipt,
                Where<POReceipt.receiptNbr, Equal<Required<POReceipt.receiptNbr>>>>
                .Select(graph, ncr.ReceiptNbr);
            if (graph.Document.Current == null)
            {
                throw new PXException("Purchase receipt {0} was not found.", ncr.ReceiptNbr);
            }
            throw new PXRedirectRequiredException(graph, "Return to Vendor");
        }
    }
}
