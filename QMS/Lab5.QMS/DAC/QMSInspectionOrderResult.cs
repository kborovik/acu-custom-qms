using System;
using PX.Data;

namespace Lab5.QMS
{
    [PXTableName]
    [Serializable]
    public class UsrQMSInspectionOrderResult : PXBqlTable, IBqlTable
    {
    }

    /// <summary>Inspection test result line. Table UsrQMSInspectionOrderResult.</summary>
    [Serializable]
    [PXCacheName("Inspection Order Result")]
    public class QMSInspectionOrderResult : UsrQMSInspectionOrderResult
    {
        #region InspectionOrderNbr
        [PXDBString(15, IsUnicode = true, IsKey = true)]
        [PXDBDefault(typeof(QMSInspectionOrder.inspectionOrderNbr))]
        [PXParent(typeof(Select<QMSInspectionOrder,
            Where<QMSInspectionOrder.inspectionOrderNbr, Equal<Current<QMSInspectionOrderResult.inspectionOrderNbr>>>>))]
        [PXUIField(DisplayName = "InspectionOrderNbr", Visible = false)]
        public virtual string InspectionOrderNbr { get; set; }
        public abstract class inspectionOrderNbr : PX.Data.BQL.BqlString.Field<inspectionOrderNbr> { }
        #endregion

        #region LineNbr
        [PXDBInt(IsKey = true)]
        [PXUIField(DisplayName = "LineNbr", Visible = false)]
        public virtual int? LineNbr { get; set; }
        public abstract class lineNbr : PX.Data.BQL.BqlInt.Field<lineNbr> { }
        #endregion

        #region TestID
        [PXDBString(30, IsUnicode = true)]
        [PXUIField(DisplayName = "TestID")]
        public virtual string TestID { get; set; }
        public abstract class testID : PX.Data.BQL.BqlString.Field<testID> { }
        #endregion

        #region TestMethod
        [PXDBString(100, IsUnicode = true)]
        [PXUIField(DisplayName = "TestMethod")]
        public virtual string TestMethod { get; set; }
        public abstract class testMethod : PX.Data.BQL.BqlString.Field<testMethod> { }
        #endregion

        #region TargetSpec
        [PXDBString(60, IsUnicode = true)]
        [PXUIField(DisplayName = "TargetSpec")]
        public virtual string TargetSpec { get; set; }
        public abstract class targetSpec : PX.Data.BQL.BqlString.Field<targetSpec> { }
        #endregion

        #region ActualNumericValue
        [PXDBDecimal(4)]
        [PXUIField(DisplayName = "ActualNumericValue")]
        public virtual decimal? ActualNumericValue { get; set; }
        public abstract class actualNumericValue : PX.Data.BQL.BqlDecimal.Field<actualNumericValue> { }
        #endregion

        #region ActualTextValue
        [PXDBString(100, IsUnicode = true)]
        [PXUIField(DisplayName = "ActualTextValue")]
        public virtual string ActualTextValue { get; set; }
        public abstract class actualTextValue : PX.Data.BQL.BqlString.Field<actualTextValue> { }
        #endregion

        #region Evaluation
        [PXDBString(1, IsFixed = true)]
        [QMSLineEvaluation.List]
        [PXUIField(DisplayName = "Evaluation")]
        public virtual string Evaluation { get; set; }
        public abstract class evaluation : PX.Data.BQL.BqlString.Field<evaluation> { }
        #endregion

        #region Notes
        [PXDBString(255, IsUnicode = true)]
        [PXUIField(DisplayName = "Notes")]
        public virtual string Notes { get; set; }
        public abstract class notes : PX.Data.BQL.BqlString.Field<notes> { }
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
        public virtual DateTime? LastModifiedDateTime { get; set; }
        public abstract class lastModifiedDateTime : PX.Data.BQL.BqlDateTime.Field<lastModifiedDateTime> { }
        #endregion
    }
}
