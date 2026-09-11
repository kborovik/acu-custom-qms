using PX.Data;

namespace Lab5.QMS
{
    public class QMSSetupMaint : PXGraph<QMSSetupMaint>
    {
        public PXSave<QMSSetup> Save;
        public PXCancel<QMSSetup> Cancel;
        public PXSelect<QMSSetup> Setup;
    }
}
