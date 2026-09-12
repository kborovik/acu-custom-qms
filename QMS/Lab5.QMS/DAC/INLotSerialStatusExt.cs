using PX.Data;
using PX.Objects.IN;

namespace Lab5.QMS
{
    /// <summary>I.lot on 26.x: INLotSerialStatus has no LotStatus; persist UsrQMSLotStatus.</summary>
    public class INLotSerialStatusExt : PXCacheExtension<INLotSerialStatus>
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
