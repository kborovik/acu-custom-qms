using System;
using PX.Data;
using PX.Objects.AP;
using PX.Objects.CS;
using PX.Objects.IN;
using PX.Objects.PO;
using PX.SM;

namespace Lab5.QMS
{
    /// <summary>Non-conformance / quarantine ticket. Table UsrQMSNonConformance (SQL synonym QMSNonConformance).</summary>
    [Serializable]
    [PXCacheName("Non-Conformance")]
    [PXPrimaryGraph(typeof(QMSNonConformanceEntry))]
    public class QMSNonConformance : PXBqlTable, IBqlTable
    {
        #region NCRNbr
        [PXDBString(15, IsUnicode = true, IsKey = true, InputMask = ">CCCCCCCCCCCCCCC")]
        [PXDefault]
        [AutoNumber(typeof(QMSSetup.nCRNumberingID), typeof(AccessInfo.businessDate))]
        [PXSelector(typeof(Search<QMSNonConformance.nCRNbr>))]
        [PXUIField(DisplayName = "NCR Nbr", Visibility = PXUIVisibility.SelectorVisible)]
        public virtual string NCRNbr { get; set; }
        public abstract class nCRNbr : PX.Data.BQL.BqlString.Field<nCRNbr> { }
        #endregion

        #region Status
        [PXDBString(1, IsFixed = true)]
        [PXDefault(QMSNonConformanceStatus.Open)]
        [QMSNonConformanceStatus.List]
        [PXUIField(DisplayName = "Status")]
        public virtual string Status { get; set; }
        public abstract class status : PX.Data.BQL.BqlString.Field<status> { }
        #endregion

        #region InspectionOrderNbr
        [PXDBString(15, IsUnicode = true)]
        [PXSelector(typeof(Search<QMSInspectionOrder.inspectionOrderNbr>))]
        [PXUIField(DisplayName = "Inspection Order Nbr")]
        public virtual string InspectionOrderNbr { get; set; }
        public abstract class inspectionOrderNbr : PX.Data.BQL.BqlString.Field<inspectionOrderNbr> { }
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

        #region Severity
        [PXDBString(1, IsFixed = true)]
        [PXDefault(QMSSeverity.Critical)]
        [QMSSeverity.List]
        [PXUIField(DisplayName = "Severity")]
        public virtual string Severity { get; set; }
        public abstract class severity : PX.Data.BQL.BqlString.Field<severity> { }
        #endregion

        #region NonConformanceType
        [PXDBString(60, IsUnicode = true)]
        [PXUIField(DisplayName = "Non-Conformance Type")]
        public virtual string NonConformanceType { get; set; }
        public abstract class nonConformanceType : PX.Data.BQL.BqlString.Field<nonConformanceType> { }
        #endregion

        #region RootCauseCategory
        [PXDBString(60, IsUnicode = true)]
        [PXUIField(DisplayName = "Root Cause Category")]
        public virtual string RootCauseCategory { get; set; }
        public abstract class rootCauseCategory : PX.Data.BQL.BqlString.Field<rootCauseCategory> { }
        #endregion

        #region AssignedQAOfficer
        [PXDBGuid]
        [PXSelector(typeof(Search<Users.pKID>), SubstituteKey = typeof(Users.username))]
        [PXUIField(DisplayName = "Assigned QA Officer")]
        public virtual Guid? AssignedQAOfficer { get; set; }
        public abstract class assignedQAOfficer : PX.Data.BQL.BqlGuid.Field<assignedQAOfficer> { }
        #endregion

        #region Description
        [PXDBString(1000, IsUnicode = true)]
        [PXUIField(DisplayName = "Description")]
        public virtual string Description { get; set; }
        public abstract class description : PX.Data.BQL.BqlString.Field<description> { }
        #endregion

        #region ActionRequired
        [PXDBString(255, IsUnicode = true)]
        [PXUIField(DisplayName = "Action Required")]
        public virtual string ActionRequired { get; set; }
        public abstract class actionRequired : PX.Data.BQL.BqlString.Field<actionRequired> { }
        #endregion

        #region InventoryHoldStatus
        [PXDBString(10, IsUnicode = false)]
        [PXDefault(QMSInventoryHoldStatus.Quarantine)]
        [QMSInventoryHoldStatus.List]
        [PXUIField(DisplayName = "Inventory Hold Status")]
        public virtual string InventoryHoldStatus { get; set; }
        public abstract class inventoryHoldStatus : PX.Data.BQL.BqlString.Field<inventoryHoldStatus> { }
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
