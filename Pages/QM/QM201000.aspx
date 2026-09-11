<%@ Page Language="C#" MasterPageFile="~/MasterPages/FormDetail.master" AutoEventWireup="true"
    ValidateRequest="false" CodeFile="QM201000.aspx.cs" Inherits="Page_QM201000" Title="Inspection Plans" %>
<%@ MasterType VirtualPath="~/MasterPages/FormDetail.master" %>

<asp:Content ID="cont1" ContentPlaceHolderID="phDS" runat="Server">
    <px:PXDataSource ID="ds" runat="server" Visible="True" Width="100%"
        TypeName="Lab5.QMS.QMSInspectionPlanMaint" PrimaryView="Document">
        <CallbackCommands />
    </px:PXDataSource>
</asp:Content>
<asp:Content ID="cont2" ContentPlaceHolderID="phF" runat="Server">
    <px:PXFormView ID="form" runat="server" DataSourceID="ds" Width="100%" DataMember="Document">
        <Template>
            <px:PXLayoutRule runat="server" StartColumn="True" LabelsWidth="SM" ControlSize="M" />
            <px:PXSelector ID="edPlanID" runat="server" DataField="PlanID" />
            <px:PXTextEdit ID="edDescription" runat="server" DataField="Description" />
            <px:PXSegmentMask ID="edInventoryID" runat="server" DataField="InventoryID" />
            <px:PXTextEdit ID="edSamplingPlan" runat="server" DataField="SamplingPlan" />
            <px:PXDropDown ID="edStatus" runat="server" DataField="Status" />
            <px:PXDateTimeEdit ID="edEffectiveDate" runat="server" DataField="EffectiveDate" />
        </Template>
    </px:PXFormView>
</asp:Content>
<asp:Content ID="cont3" ContentPlaceHolderID="phG" runat="Server">
    <px:PXGrid ID="grid" runat="server" DataSourceID="ds" Width="100%" Height="150px"
        SkinID="Details" SyncPosition="True">
        <Levels>
            <px:PXGridLevel DataMember="Tests">
                <Columns>
                    <px:PXGridColumn DataField="LineNbr" Width="70px" />
                    <px:PXGridColumn DataField="TestID" Width="140px" />
                    <px:PXGridColumn DataField="Description" Width="220px" />
                    <px:PXGridColumn DataField="TestMethod" Width="180px" />
                    <px:PXGridColumn DataField="TargetValue" Width="100px" />
                    <px:PXGridColumn DataField="MinValue" Width="100px" />
                    <px:PXGridColumn DataField="MaxValue" Width="100px" />
                    <px:PXGridColumn DataField="UOM" Width="80px" />
                    <px:PXGridColumn DataField="Criticality" Width="80px" />
                </Columns>
            </px:PXGridLevel>
        </Levels>
        <AutoSize Container="Window" Enabled="True" MinHeight="150" />
    </px:PXGrid>
</asp:Content>
