<%@ Page Language="C#" MasterPageFile="~/MasterPages/FormDetail.master" AutoEventWireup="true"
    ValidateRequest="false" CodeFile="QM301000.aspx.cs" Inherits="Page_QM301000" Title="Inspection Orders" %>
<%@ MasterType VirtualPath="~/MasterPages/FormDetail.master" %>

<asp:Content ID="cont1" ContentPlaceHolderID="phDS" runat="Server">
    <px:PXDataSource ID="ds" runat="server" Visible="True" Width="100%"
        TypeName="Lab5.QMS.QMSInspectionOrderEntry" PrimaryView="Document">
        <CallbackCommands>
            <px:PXDSCallbackCommand Name="EvaluateResults" CommitChanges="True" />
        </CallbackCommands>
    </px:PXDataSource>
</asp:Content>
<asp:Content ID="cont2" ContentPlaceHolderID="phF" runat="Server">
    <px:PXFormView ID="form" runat="server" DataSourceID="ds" Width="100%" DataMember="Document">
        <Template>
            <px:PXLayoutRule runat="server" StartColumn="True" LabelsWidth="SM" ControlSize="M" />
            <px:PXSelector ID="edInspectionOrderNbr" runat="server" DataField="InspectionOrderNbr" />
            <px:PXDropDown ID="edStatus" runat="server" DataField="Status" />
            <px:PXSegmentMask ID="edInventoryID" runat="server" DataField="InventoryID" />
            <px:PXTextEdit ID="edLotSerialNbr" runat="server" DataField="LotSerialNbr" />
            <px:PXSegmentMask ID="edVendorID" runat="server" DataField="VendorID" />
            <px:PXSelector ID="edReceiptNbr" runat="server" DataField="ReceiptNbr" />
            <px:PXSelector ID="edPlanID" runat="server" DataField="PlanID" />
            <px:PXTextEdit ID="edTestingLabID" runat="server" DataField="TestingLabID" />
            <px:PXTextEdit ID="edLabCertificateNbr" runat="server" DataField="LabCertificateNbr" />
            <px:PXDropDown ID="edOverallEvaluation" runat="server" DataField="OverallEvaluation" />
        </Template>
    </px:PXFormView>
</asp:Content>
<asp:Content ID="cont3" ContentPlaceHolderID="phG" runat="Server">
    <px:PXGrid ID="grid" runat="server" DataSourceID="ds" Width="100%" Height="150px"
        SkinID="Details" SyncPosition="True">
        <Levels>
            <px:PXGridLevel DataMember="Results">
                <Columns>
                    <px:PXGridColumn DataField="LineNbr" Width="70px" />
                    <px:PXGridColumn DataField="TestID" Width="140px" />
                    <px:PXGridColumn DataField="TestMethod" Width="180px" />
                    <px:PXGridColumn DataField="TargetSpec" Width="140px" />
                    <px:PXGridColumn DataField="ActualNumericValue" Width="120px" />
                    <px:PXGridColumn DataField="ActualTextValue" Width="160px" />
                    <px:PXGridColumn DataField="Evaluation" Width="80px" />
                    <px:PXGridColumn DataField="Notes" Width="200px" />
                </Columns>
            </px:PXGridLevel>
        </Levels>
        <AutoSize Container="Window" Enabled="True" MinHeight="150" />
    </px:PXGrid>
</asp:Content>
