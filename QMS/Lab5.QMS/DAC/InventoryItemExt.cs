using PX.Data;
using PX.Objects.IN;

namespace Lab5.QMS
{
    public class InventoryItemExt : PXCacheExtension<InventoryItem>
    {
        #region UsrQMSInspectionRequired
        [PXDBBool]
        [PXDefault(false)]
        [PXUIField(DisplayName = "UsrQMSInspectionRequired")]
        public virtual bool? UsrQMSInspectionRequired { get; set; }
        public abstract class usrQMSInspectionRequired : PX.Data.BQL.BqlBool.Field<usrQMSInspectionRequired> { }
        #endregion

        #region UsrQMSInspectionPlanID
        [PXDBString(30, IsUnicode = true)]
        [PXSelector(typeof(Search<QMSInspectionPlan.planID,
            Where<QMSInspectionPlan.status, Equal<QMSInspectionPlanStatus.active>>>),
            DescriptionField = typeof(QMSInspectionPlan.description))]
        [PXUIField(DisplayName = "InspectionPlan")]
        public virtual string UsrQMSInspectionPlanID { get; set; }
        public abstract class usrQMSInspectionPlanID : PX.Data.BQL.BqlString.Field<usrQMSInspectionPlanID> { }
        #endregion

        #region UsrMinShelfLifeDays
        [PXDBInt]
        [PXDefault(0)]
        [PXUIField(DisplayName = "UsrMinShelfLifeDays")]
        public virtual int? UsrMinShelfLifeDays { get; set; }
        public abstract class usrMinShelfLifeDays : PX.Data.BQL.BqlInt.Field<usrMinShelfLifeDays> { }
        #endregion
    }
}
