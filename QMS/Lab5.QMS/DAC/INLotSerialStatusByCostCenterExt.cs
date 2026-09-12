using PX.Data;
using PX.Objects.IN;

namespace Lab5.QMS
{
    /// <summary>26.x live lot rows are INLotSerialStatusByCostCenter; persist UsrQMSLotStatus there.</summary>
    public class INLotSerialStatusByCostCenterExt : PXCacheExtension<INLotSerialStatusByCostCenter>
    {
        public static bool IsActive()
        {
            return true;
        }

        #region UsrQMSLotStatus
        [PXDBString(10, IsUnicode = true)]
        [PXUIField(DisplayName = "UsrQMSLotStatus")]
        public virtual string UsrQMSLotStatus { get; set; }
        public abstract class usrQMSLotStatus : PX.Data.BQL.BqlString.Field<usrQMSLotStatus> { }
        #endregion
    }
}
