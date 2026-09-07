using System;
using PX.Data;
using PX.Objects.CS;

namespace Lab5.QMS
{
    /// <summary>
    /// PX schema-cache table name for <see cref="QMSSetup"/>.
    /// Synonyms are not tables; PUT Locate/Insert looks up this name.
    /// </summary>
    [PXTableName]
    [Serializable]
    public class UsrQMSSetup : PXBqlTable, IBqlTable
    {
    }

    /// <summary>Quality Preferences. Table UsrQMSSetup.</summary>
    [Serializable]
    [PXCacheName("Quality Preferences")]
    [PXPrimaryGraph(typeof(QMSSetupMaint))]
    public class QMSSetup : UsrQMSSetup
    {
        #region InspectionOrderNumberingID
        [PXDBString(10, IsUnicode = true)]
        [PXDefault(QMSSetupRules.InspectionOrderNumberingID)]
        [PXSelector(typeof(Numbering.numberingID), DescriptionField = typeof(Numbering.descr))]
        [PXUIField(DisplayName = "Inspection Order Numbering Sequence")]
        public virtual string InspectionOrderNumberingID { get; set; }
        public abstract class inspectionOrderNumberingID : PX.Data.BQL.BqlString.Field<inspectionOrderNumberingID> { }
        #endregion

        #region NCRNumberingID
        [PXDBString(10, IsUnicode = true)]
        [PXDefault(QMSSetupRules.NcrNumberingID)]
        [PXSelector(typeof(Numbering.numberingID), DescriptionField = typeof(Numbering.descr))]
        [PXUIField(DisplayName = "NCR Numbering Sequence")]
        public virtual string NCRNumberingID { get; set; }
        public abstract class nCRNumberingID : PX.Data.BQL.BqlString.Field<nCRNumberingID> { }
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
