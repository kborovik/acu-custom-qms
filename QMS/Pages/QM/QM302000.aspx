<%@ Page Language="C#" MasterPageFile="~/MasterPages/FormView.master" AutoEventWireup="true"
    ValidateRequest="false" CodeFile="QM302000.aspx.cs" Inherits="Page_QM302000" Title="Non-Conformance Reports" %>
<%@ MasterType VirtualPath="~/MasterPages/FormView.master" %>

<asp:Content ID="cont1" ContentPlaceHolderID="phDS" runat="Server">
    <px:PXDataSource ID="ds" runat="server" Visible="True" Width="100%"
        TypeName="Lab5.QMS.QMSNonConformanceEntry" PrimaryView="Document">
        <CallbackCommands>
            <px:PXDSCallbackCommand Name="CloseNCR" CommitChanges="True" />
            <px:PXDSCallbackCommand Name="DispositionRTV" CommitChanges="True" />
        </CallbackCommands>
    </px:PXDataSource>
</asp:Content>
<asp:Content ID="cont2" ContentPlaceHolderID="phF" runat="Server">
    <px:PXFormView ID="form" runat="server" DataSourceID="ds" Width="100%" DataMember="Document">
        <Template>
            <px:PXLayoutRule runat="server" StartColumn="True" LabelsWidth="SM" ControlSize="M" />
            <px:PXSelector ID="edNCRNbr" runat="server" DataField="NCRNbr" />
            <px:PXDropDown ID="edStatus" runat="server" DataField="Status" />
            <px:PXSelector ID="edInspectionOrderNbr" runat="server" DataField="InspectionOrderNbr" />
            <px:PXSegmentMask ID="edInventoryID" runat="server" DataField="InventoryID" />
            <px:PXTextEdit ID="edLotSerialNbr" runat="server" DataField="LotSerialNbr" />
            <px:PXSegmentMask ID="edVendorID" runat="server" DataField="VendorID" />
            <px:PXSelector ID="edReceiptNbr" runat="server" DataField="ReceiptNbr" AllowEdit="True" />
            <px:PXLayoutRule runat="server" StartColumn="True" LabelsWidth="SM" ControlSize="M" />
            <px:PXDropDown ID="edSeverity" runat="server" DataField="Severity" />
            <px:PXTextEdit ID="edNonConformanceType" runat="server" DataField="NonConformanceType" />
            <px:PXTextEdit ID="edRootCauseCategory" runat="server" DataField="RootCauseCategory" />
            <px:PXSelector ID="edAssignedQAOfficer" runat="server" DataField="AssignedQAOfficer" />
            <px:PXDropDown ID="edInventoryHoldStatus" runat="server" DataField="InventoryHoldStatus" />
            <px:PXTextEdit ID="edActionRequired" runat="server" DataField="ActionRequired" />
            <px:PXTextEdit ID="edDescription" runat="server" DataField="Description" TextMode="MultiLine" Height="60px" />
        </Template>
    </px:PXFormView>
</asp:Content>
