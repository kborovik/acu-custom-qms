using System;
using PX.Data;
using PX.Objects.AP;
using PX.Objects.CS;
using PX.Objects.IN;
using PX.Objects.PO;
using PX.SM;

namespace Lab5.QMS
{
    /// <summary>
    /// PX schema-cache table name for <see cref="QMSInspectionOrder"/>.
    /// Synonyms are not tables; PUT Locate/Insert looks up this name.
    /// </summary>
    [PXTableName]
    [Serializable]
    public class UsrQMSInspectionOrder : PXBqlTable, IBqlTable
    {
    }

    /// <summary>Inspection order header. Table UsrQMSInspectionOrder.</summary>
    [Serializable]
    [PXCacheName("Inspection Order")]
    [PXPrimaryGraph(typeof(QMSInspectionOrderEntry))]
    public class QMSInspectionOrder : UsrQMSInspectionOrder
    {
        #region InspectionOrderNbr
        [PXDBString(15, IsUnicode = true, IsKey = true, InputMask = ">CCCCCCCCCCCCCCC")]
        [PXDefault]
        [AutoNumber(typeof(QMSSetup.inspectionOrderNumberingID), typeof(AccessInfo.businessDate))]
        [PXSelector(typeof(Search<QMSInspectionOrder.inspectionOrderNbr>))]
        [PXUIField(DisplayName = "Inspection Order Nbr", Visibility = PXUIVisibility.SelectorVisible)]
        public virtual string InspectionOrderNbr { get; set; }
        public abstract class inspectionOrderNbr : PX.Data.BQL.BqlString.Field<inspectionOrderNbr> { }
        #endregion

        #region Status
        [PXDBString(1, IsFixed = true)]
        [PXDefault(QMSInspectionOrderStatus.Open)]
        [QMSInspectionOrderStatus.List]
        [PXUIField(DisplayName = "Status")]
        public virtual string Status { get; set; }
        public abstract class status : PX.Data.BQL.BqlString.Field<status> { }
        #endregion

        #region InventoryID
        [PXDBInt]
        [PXSelector(typeof(Search<InventoryItem.inventoryID>),
            typeof(InventoryItem.inventoryCD),
            typeof(InventoryItem.descr),
            SubstituteKey = typeof(InventoryItem.inventoryCD))]
        [PXUIField(DisplayName = "Inventory ID")]
        public virtual int? InventoryID { get; set; }
        public abstract class inventoryID : PX.Data.BQL.BqlInt.Field<inventoryID> { }
        #endregion

        #region LotSerialNbr
        [PXDBString(50, IsUnicode = true)]
        [PXUIField(DisplayName = "Lot/Serial Nbr")]
        public virtual string LotSerialNbr { get; set; }
        public abstract class lotSerialNbr : PX.Data.BQL.BqlString.Field<lotSerialNbr> { }
        #endregion

        #region VendorID
        [PXDBInt]
        [PXSelector(typeof(Search<Vendor.bAccountID>),
            typeof(Vendor.acctCD),
            typeof(Vendor.acctName),
            SubstituteKey = typeof(Vendor.acctCD))]
        [PXUIField(DisplayName = "Vendor")]
        public virtual int? VendorID { get; set; }
        public abstract class vendorID : PX.Data.BQL.BqlInt.Field<vendorID> { }
        #endregion

        #region ReceiptNbr
        [PXDBString(15, IsUnicode = true)]
        [PXSelector(typeof(Search<POReceipt.receiptNbr>))]
        [PXUIField(DisplayName = "Receipt Nbr")]
        public virtual string ReceiptNbr { get; set; }
        public abstract class receiptNbr : PX.Data.BQL.BqlString.Field<receiptNbr> { }
        #endregion

        #region PlanID
        [PXDBString(30, IsUnicode = true)]
        [PXSelector(typeof(Search<QMSInspectionPlan.planID>),
            DescriptionField = typeof(QMSInspectionPlan.description))]
        [PXUIField(DisplayName = "Plan ID")]
        public virtual string PlanID { get; set; }
        public abstract class planID : PX.Data.BQL.BqlString.Field<planID> { }
        #endregion

        #region TestingLabID
        [PXDBString(30, IsUnicode = true)]
        [PXUIField(DisplayName = "Testing Lab")]
        public virtual string TestingLabID { get; set; }
        public abstract class testingLabID : PX.Data.BQL.BqlString.Field<testingLabID> { }
        #endregion

        #region LabCertificateNbr
        [PXDBString(60, IsUnicode = true)]
        [PXUIField(DisplayName = "Lab Certificate Nbr")]
        public virtual string LabCertificateNbr { get; set; }
        public abstract class labCertificateNbr : PX.Data.BQL.BqlString.Field<labCertificateNbr> { }
        #endregion

        #region InspectionDate
        [PXDBDate]
        [PXUIField(DisplayName = "Inspection Date")]
        public virtual DateTime? InspectionDate { get; set; }
        public abstract class inspectionDate : PX.Data.BQL.BqlDateTime.Field<inspectionDate> { }
        #endregion

        #region OverallEvaluation
        [PXDBString(1, IsFixed = true)]
        [PXDefault(QMSOverallEvaluation.Pending)]
        [QMSOverallEvaluation.List]
        [PXUIField(DisplayName = "Overall Evaluation")]
        public virtual string OverallEvaluation { get; set; }
        public abstract class overallEvaluation : PX.Data.BQL.BqlString.Field<overallEvaluation> { }
        #endregion

        #region EvaluatedByID
        [PXDBGuid]
        [PXSelector(typeof(Search<Users.pKID>), SubstituteKey = typeof(Users.username))]
        [PXUIField(DisplayName = "Evaluated By", Enabled = false)]
        public virtual Guid? EvaluatedByID { get; set; }
        public abstract class evaluatedByID : PX.Data.BQL.BqlGuid.Field<evaluatedByID> { }
        #endregion

        #region EvaluationDateTime
        [PXDBDateAndTime]
        [PXUIField(DisplayName = "Evaluated On", Enabled = false)]
        public virtual DateTime? EvaluationDateTime { get; set; }
        public abstract class evaluationDateTime : PX.Data.BQL.BqlDateTime.Field<evaluationDateTime> { }
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
        [PXUIField(DisplayName = "Created On", Enabled = false)]
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
        [PXUIField(DisplayName = "Last Modified On", Enabled = false)]
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
