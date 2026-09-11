<%@ Page Language="C#" MasterPageFile="~/MasterPages/FormView.master" AutoEventWireup="true"
    ValidateRequest="false" CodeFile="QM101000.aspx.cs" Inherits="Page_QM101000" Title="Quality Preferences" %>
<%@ MasterType VirtualPath="~/MasterPages/FormView.master" %>

<asp:Content ID="cont1" ContentPlaceHolderID="phDS" runat="Server">
    <px:PXDataSource ID="ds" runat="server" Visible="True" Width="100%"
        TypeName="Lab5.QMS.QMSSetupMaint" PrimaryView="Setup">
        <CallbackCommands />
    </px:PXDataSource>
</asp:Content>
<asp:Content ID="cont2" ContentPlaceHolderID="phF" runat="Server">
    <px:PXFormView ID="form" runat="server" DataSourceID="ds" Width="100%" DataMember="Setup">
        <Template>
            <px:PXLayoutRule runat="server" StartColumn="True" LabelsWidth="M" ControlSize="M" />
            <px:PXSelector ID="edInspectionOrderNumberingID" runat="server" DataField="InspectionOrderNumberingID" />
            <px:PXSelector ID="edNCRNumberingID" runat="server" DataField="NCRNumberingID" />
        </Template>
    </px:PXFormView>
</asp:Content>
