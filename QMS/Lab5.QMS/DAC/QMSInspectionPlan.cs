using System;
using PX.Data;
using PX.Objects.IN;

namespace Lab5.QMS
{
    /// <summary>[PXTableName] binds persist to physical UsrQMS* table.</summary>
    [PXTableName]
    [Serializable]
    public class UsrQMSInspectionPlan : PXBqlTable, IBqlTable
    {
    }

    /// <summary>Inspection plan master. Table UsrQMSInspectionPlan.</summary>
    [Serializable]
    [PXCacheName("Inspection Plan")]
    [PXPrimaryGraph(typeof(QMSInspectionPlanMaint))]
    public class QMSInspectionPlan : UsrQMSInspectionPlan
    {
        #region PlanID
        [PXDBString(30, IsUnicode = true, IsKey = true, InputMask = ">CCCCCCCCCCCCCCCCCCCCCCCCCCCCCC")]
        [PXDefault]
        [PXSelector(typeof(Search<QMSInspectionPlan.planID>), ValidateValue = false)]
        [PXUIField(DisplayName = "PlanID", Visibility = PXUIVisibility.SelectorVisible)]
        public virtual string PlanID { get; set; }
        public abstract class planID : PX.Data.BQL.BqlString.Field<planID> { }
        #endregion

        #region Description
        [PXDBString(255, IsUnicode = true)]
        [PXUIField(DisplayName = "Description", Visibility = PXUIVisibility.SelectorVisible)]
        public virtual string Description { get; set; }
        public abstract class description : PX.Data.BQL.BqlString.Field<description> { }
        #endregion

        #region InventoryID
        [PXDBInt]
        [PXSelector(typeof(Search<InventoryItem.inventoryID>),
            typeof(InventoryItem.inventoryCD),
            typeof(InventoryItem.descr),
            SubstituteKey = typeof(InventoryItem.inventoryCD))]
        [PXUIField(DisplayName = "InventoryID")]
        public virtual int? InventoryID { get; set; }
        public abstract class inventoryID : PX.Data.BQL.BqlInt.Field<inventoryID> { }
        #endregion

        #region SamplingPlan
        [PXDBString(100, IsUnicode = true)]
        [PXUIField(DisplayName = "SamplingPlan")]
        public virtual string SamplingPlan { get; set; }
        public abstract class samplingPlan : PX.Data.BQL.BqlString.Field<samplingPlan> { }
        #endregion

        #region Status
        [PXDBString(1, IsFixed = true)]
        [PXDefault(QMSInspectionPlanStatus.Active)]
        [QMSInspectionPlanStatus.List]
        [PXUIField(DisplayName = "Status")]
        public virtual string Status { get; set; }
        public abstract class status : PX.Data.BQL.BqlString.Field<status> { }
        #endregion

        #region RevisionID
        [PXDBInt]
        [PXDefault(1)]
        [PXUIField(DisplayName = "RevisionID")]
        public virtual int? RevisionID { get; set; }
        public abstract class revisionID : PX.Data.BQL.BqlInt.Field<revisionID> { }
        #endregion

        #region EffectiveDate
        [PXDBDate]
        [PXUIField(DisplayName = "EffectiveDate")]
        public virtual DateTime? EffectiveDate { get; set; }
        public abstract class effectiveDate : PX.Data.BQL.BqlDateTime.Field<effectiveDate> { }
        #endregion

        #region tstamp
        [PXDBTimestamp]
        public virtual byte[] tstamp { get; set; }
        public abstract class Tstamp : PX.Data.BQL.BqlByteArray.Field<Tstamp> { }
        #endregion

        #region CreatedByID
        [PXDBCreatedByID]
        public virtual Guid? CreatedByID { get; set; }
        public abstract class createdByID : PX.Data.BQL.BqlGuid.Field<createdByID> { }
        #endregion

        #region CreatedByScreenID
        [PXDBCreatedByScreenID]
        public virtual string CreatedByScreenID { get; set; }
        public abstract class createdByScreenID : PX.Data.BQL.BqlString.Field<createdByScreenID> { }
        #endregion

        #region CreatedDateTime
        [PXDBCreatedDateTime]
        [PXUIField(DisplayName = "CreatedDateTime", Enabled = false)]
        public virtual DateTime? CreatedDateTime { get; set; }
        public abstract class createdDateTime : PX.Data.BQL.BqlDateTime.Field<createdDateTime> { }
        #endregion

        #region LastModifiedByID
        [PXDBLastModifiedByID]
        public virtual Guid? LastModifiedByID { get; set; }
        public abstract class lastModifiedByID : PX.Data.BQL.BqlGuid.Field<lastModifiedByID> { }
        #endregion

        #region LastModifiedByScreenID
        [PXDBLastModifiedByScreenID]
        public virtual string LastModifiedByScreenID { get; set; }
        public abstract class lastModifiedByScreenID : PX.Data.BQL.BqlString.Field<lastModifiedByScreenID> { }
        #endregion

        #region LastModifiedDateTime
        [PXDBLastModifiedDateTime]
        [PXUIField(DisplayName = "LastModifiedDateTime", Enabled = false)]
        public virtual DateTime? LastModifiedDateTime { get; set; }
        public abstract class lastModifiedDateTime : PX.Data.BQL.BqlDateTime.Field<lastModifiedDateTime> { }
        #endregion

        #region NoteID
        [PXNote]
        public virtual Guid? NoteID { get; set; }
        public abstract class noteID : PX.Data.BQL.BqlGuid.Field<noteID> { }
        #endregion
    }
}
