using System;
using PX.Data;

namespace Lab5.QMS
{
    [PXTableName]
    [Serializable]
    public class UsrQMSInspectionPlanTest : PXBqlTable, IBqlTable
    {
    }

    /// <summary>Plan test criteria line. Table UsrQMSInspectionPlanTest.</summary>
    [Serializable]
    [PXCacheName("Inspection Plan Test")]
    public class QMSInspectionPlanTest : UsrQMSInspectionPlanTest
    {
        #region PlanID
        [PXDBString(30, IsUnicode = true, IsKey = true)]
        [PXDBDefault(typeof(QMSInspectionPlan.planID))]
        [PXParent(typeof(Select<QMSInspectionPlan,
            Where<QMSInspectionPlan.planID, Equal<Current<QMSInspectionPlanTest.planID>>>>))]
        [PXUIField(DisplayName = "Plan ID", Visible = false)]
        public virtual string PlanID { get; set; }
        public abstract class planID : PX.Data.BQL.BqlString.Field<planID> { }
        #endregion

        #region LineNbr
        [PXDBInt(IsKey = true)]
        [PXUIField(DisplayName = "Line Nbr")]
        public virtual int? LineNbr { get; set; }
        public abstract class lineNbr : PX.Data.BQL.BqlInt.Field<lineNbr> { }
        #endregion

        #region TestID
        [PXDBString(30, IsUnicode = true)]
        [PXUIField(DisplayName = "Test ID")]
        public virtual string TestID { get; set; }
        public abstract class testID : PX.Data.BQL.BqlString.Field<testID> { }
        #endregion

        #region Description
        [PXDBString(120, IsUnicode = true)]
        [PXUIField(DisplayName = "Description")]
        public virtual string Description { get; set; }
        public abstract class description : PX.Data.BQL.BqlString.Field<description> { }
        #endregion

        #region TestMethod
        [PXDBString(100, IsUnicode = true)]
        [PXUIField(DisplayName = "Test Method")]
        public virtual string TestMethod { get; set; }
        public abstract class testMethod : PX.Data.BQL.BqlString.Field<testMethod> { }
        #endregion

        #region TargetValue
        [PXDBDecimal(4)]
        [PXUIField(DisplayName = "Target")]
        public virtual decimal? TargetValue { get; set; }
        public abstract class targetValue : PX.Data.BQL.BqlDecimal.Field<targetValue> { }
        #endregion

        #region MinValue
        [PXDBDecimal(4)]
        [PXUIField(DisplayName = "Min. Value")]
        public virtual decimal? MinValue { get; set; }
        public abstract class minValue : PX.Data.BQL.BqlDecimal.Field<minValue> { }
        #endregion

        #region MaxValue
        [PXDBDecimal(4)]
        [PXUIField(DisplayName = "Max. Value")]
        public virtual decimal? MaxValue { get; set; }
        public abstract class maxValue : PX.Data.BQL.BqlDecimal.Field<maxValue> { }
        #endregion

        #region UOM
        [PXDBString(20, IsUnicode = true)]
        [PXUIField(DisplayName = "UOM")]
        public virtual string UOM { get; set; }
        public abstract class uOM : PX.Data.BQL.BqlString.Field<uOM> { }
        #endregion

        #region Criticality
        [PXDBString(1, IsFixed = true)]
        [PXDefault(QMSCriticality.Critical)]
        [QMSCriticality.List]
        [PXUIField(DisplayName = "Criticality")]
        public virtual string Criticality { get; set; }
        public abstract class criticality : PX.Data.BQL.BqlString.Field<criticality> { }
        #endregion

        #region IsRequired
        [PXDBBool]
        [PXDefault(true)]
        [PXUIField(DisplayName = "Required")]
        public virtual bool? IsRequired { get; set; }
        public abstract class isRequired : PX.Data.BQL.BqlBool.Field<isRequired> { }
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

    public static class QMSCriticality
    {
        public const string Critical = "C";
        public const string Major = "M";
        public const string Minor = "m";

        public class ListAttribute : PXStringListAttribute
        {
            public ListAttribute()
                : base(
                    new[] { Critical, Major, Minor },
                    new[] { "Critical", "Major", "Minor" })
            {
            }
        }
    }
}
