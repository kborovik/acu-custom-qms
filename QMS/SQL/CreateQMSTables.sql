--[mssql: Native]
--[mysql: Skip]
-- UsrQMS* tables for Lab5.QMS (I.pkg CreateQMSTables.sql).
-- Re-runnable: each CREATE is gated on OBJECT_ID.

IF OBJECT_ID(N'dbo.UsrQMSInspectionPlan', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[UsrQMSInspectionPlan] (
        [CompanyID] [int] NOT NULL,
        [PlanID] [nvarchar](30) NOT NULL,
        [Description] [nvarchar](255) NULL,
        [InventoryID] [int] NULL,
        [SamplingPlan] [nvarchar](100) NULL,
        [Status] [char](1) NOT NULL,
        [RevisionID] [int] NOT NULL CONSTRAINT [DF_UsrQMSInspectionPlan_RevisionID] DEFAULT ((1)),
        [EffectiveDate] [datetime] NULL,
        [tstamp] [timestamp] NOT NULL,
        [CreatedByID] [uniqueidentifier] NOT NULL,
        [CreatedByScreenID] [char](8) NOT NULL,
        [CreatedDateTime] [datetime] NOT NULL,
        [LastModifiedByID] [uniqueidentifier] NOT NULL,
        [LastModifiedByScreenID] [char](8) NOT NULL,
        [LastModifiedDateTime] [datetime] NOT NULL,
        [NoteID] [uniqueidentifier] NULL,
        CONSTRAINT [UsrQMSInspectionPlan_PK] PRIMARY KEY CLUSTERED
        (
            [CompanyID] ASC,
            [PlanID] ASC
        )
    );
END

IF OBJECT_ID(N'dbo.UsrQMSInspectionPlanTest', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[UsrQMSInspectionPlanTest] (
        [CompanyID] [int] NOT NULL,
        [PlanID] [nvarchar](30) NOT NULL,
        [LineNbr] [int] NOT NULL,
        [TestID] [nvarchar](30) NULL,
        [Description] [nvarchar](120) NULL,
        [TestMethod] [nvarchar](100) NULL,
        [TargetValue] [decimal](19, 4) NULL,
        [MinValue] [decimal](19, 4) NULL,
        [MaxValue] [decimal](19, 4) NULL,
        [UOM] [nvarchar](20) NULL,
        [Criticality] [char](1) NOT NULL CONSTRAINT [DF_UsrQMSInspectionPlanTest_Criticality] DEFAULT ('C'),
        [IsRequired] [bit] NOT NULL CONSTRAINT [DF_UsrQMSInspectionPlanTest_IsRequired] DEFAULT ((1)),
        [tstamp] [timestamp] NOT NULL,
        [CreatedByID] [uniqueidentifier] NOT NULL,
        [CreatedByScreenID] [char](8) NOT NULL,
        [CreatedDateTime] [datetime] NOT NULL,
        [LastModifiedByID] [uniqueidentifier] NOT NULL,
        [LastModifiedByScreenID] [char](8) NOT NULL,
        [LastModifiedDateTime] [datetime] NOT NULL,
        CONSTRAINT [UsrQMSInspectionPlanTest_PK] PRIMARY KEY CLUSTERED
        (
            [CompanyID] ASC,
            [PlanID] ASC,
            [LineNbr] ASC
        )
    );
END

-- DAC class names match I.dac; tables stay UsrQMS*. Synonyms bind BQL to Usr tables.
IF OBJECT_ID(N'dbo.QMSInspectionPlan', N'SN') IS NULL
    AND OBJECT_ID(N'dbo.QMSInspectionPlan', N'U') IS NULL
    AND OBJECT_ID(N'dbo.UsrQMSInspectionPlan', N'U') IS NOT NULL
    CREATE SYNONYM [dbo].[QMSInspectionPlan] FOR [dbo].[UsrQMSInspectionPlan];

IF OBJECT_ID(N'dbo.QMSInspectionPlanTest', N'SN') IS NULL
    AND OBJECT_ID(N'dbo.QMSInspectionPlanTest', N'U') IS NULL
    AND OBJECT_ID(N'dbo.UsrQMSInspectionPlanTest', N'U') IS NOT NULL
    CREATE SYNONYM [dbo].[QMSInspectionPlanTest] FOR [dbo].[UsrQMSInspectionPlanTest];

IF OBJECT_ID(N'dbo.UsrQMSInspectionOrder', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[UsrQMSInspectionOrder] (
        [CompanyID] [int] NOT NULL,
        [InspectionOrderNbr] [nvarchar](15) NOT NULL,
        [Status] [char](1) NOT NULL,
        [InventoryID] [int] NULL,
        [LotSerialNbr] [nvarchar](50) NULL,
        [VendorID] [int] NULL,
        [ReceiptNbr] [nvarchar](15) NULL,
        [PlanID] [nvarchar](30) NULL,
        [TestingLabID] [nvarchar](30) NULL,
        [LabCertificateNbr] [nvarchar](60) NULL,
        [InspectionDate] [datetime] NULL,
        [OverallEvaluation] [char](1) NULL,
        [EvaluatedByID] [uniqueidentifier] NULL,
        [EvaluationDateTime] [datetime] NULL,
        [tstamp] [timestamp] NOT NULL,
        [CreatedByID] [uniqueidentifier] NOT NULL,
        [CreatedByScreenID] [char](8) NOT NULL,
        [CreatedDateTime] [datetime] NOT NULL,
        [LastModifiedByID] [uniqueidentifier] NOT NULL,
        [LastModifiedByScreenID] [char](8) NOT NULL,
        [LastModifiedDateTime] [datetime] NOT NULL,
        [NoteID] [uniqueidentifier] NULL,
        CONSTRAINT [UsrQMSInspectionOrder_PK] PRIMARY KEY CLUSTERED
        (
            [CompanyID] ASC,
            [InspectionOrderNbr] ASC
        )
    );
END

IF OBJECT_ID(N'dbo.UsrQMSInspectionOrderResult', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[UsrQMSInspectionOrderResult] (
        [CompanyID] [int] NOT NULL,
        [InspectionOrderNbr] [nvarchar](15) NOT NULL,
        [LineNbr] [int] NOT NULL,
        [TestID] [nvarchar](30) NULL,
        [TestMethod] [nvarchar](100) NULL,
        [TargetSpec] [nvarchar](60) NULL,
        [ActualNumericValue] [decimal](19, 4) NULL,
        [ActualTextValue] [nvarchar](100) NULL,
        [Evaluation] [char](1) NULL,
        [Notes] [nvarchar](255) NULL,
        [tstamp] [timestamp] NOT NULL,
        [CreatedByID] [uniqueidentifier] NOT NULL,
        [CreatedByScreenID] [char](8) NOT NULL,
        [CreatedDateTime] [datetime] NOT NULL,
        [LastModifiedByID] [uniqueidentifier] NOT NULL,
        [LastModifiedByScreenID] [char](8) NOT NULL,
        [LastModifiedDateTime] [datetime] NOT NULL,
        CONSTRAINT [UsrQMSInspectionOrderResult_PK] PRIMARY KEY CLUSTERED
        (
            [CompanyID] ASC,
            [InspectionOrderNbr] ASC,
            [LineNbr] ASC
        )
    );
END

IF OBJECT_ID(N'dbo.QMSInspectionOrder', N'SN') IS NULL
    AND OBJECT_ID(N'dbo.QMSInspectionOrder', N'U') IS NULL
    AND OBJECT_ID(N'dbo.UsrQMSInspectionOrder', N'U') IS NOT NULL
    CREATE SYNONYM [dbo].[QMSInspectionOrder] FOR [dbo].[UsrQMSInspectionOrder];

IF OBJECT_ID(N'dbo.QMSInspectionOrderResult', N'SN') IS NULL
    AND OBJECT_ID(N'dbo.QMSInspectionOrderResult', N'U') IS NULL
    AND OBJECT_ID(N'dbo.UsrQMSInspectionOrderResult', N'U') IS NOT NULL
    CREATE SYNONYM [dbo].[QMSInspectionOrderResult] FOR [dbo].[UsrQMSInspectionOrderResult];

IF OBJECT_ID(N'dbo.UsrQMSNonConformance', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[UsrQMSNonConformance] (
        [CompanyID] [int] NOT NULL,
        [NCRNbr] [nvarchar](15) NOT NULL,
        [Status] [char](1) NOT NULL,
        [InspectionOrderNbr] [nvarchar](15) NULL,
        [InventoryID] [int] NULL,
        [LotSerialNbr] [nvarchar](50) NULL,
        [VendorID] [int] NULL,
        [ReceiptNbr] [nvarchar](15) NULL,
        [Severity] [char](1) NULL,
        [NonConformanceType] [nvarchar](60) NULL,
        [RootCauseCategory] [nvarchar](60) NULL,
        [AssignedQAOfficer] [uniqueidentifier] NULL,
        [Description] [nvarchar](1000) NULL,
        [ActionRequired] [nvarchar](255) NULL,
        [InventoryHoldStatus] [varchar](10) NULL,
        [tstamp] [timestamp] NOT NULL,
        [CreatedByID] [uniqueidentifier] NOT NULL,
        [CreatedByScreenID] [char](8) NOT NULL,
        [CreatedDateTime] [datetime] NOT NULL,
        [LastModifiedByID] [uniqueidentifier] NOT NULL,
        [LastModifiedByScreenID] [char](8) NOT NULL,
        [LastModifiedDateTime] [datetime] NOT NULL,
        [NoteID] [uniqueidentifier] NULL,
        CONSTRAINT [UsrQMSNonConformance_PK] PRIMARY KEY CLUSTERED
        (
            [CompanyID] ASC,
            [NCRNbr] ASC
        )
    );
END

IF OBJECT_ID(N'dbo.QMSNonConformance', N'SN') IS NULL
    AND OBJECT_ID(N'dbo.QMSNonConformance', N'U') IS NULL
    AND OBJECT_ID(N'dbo.UsrQMSNonConformance', N'U') IS NOT NULL
    CREATE SYNONYM [dbo].[QMSNonConformance] FOR [dbo].[UsrQMSNonConformance];

IF OBJECT_ID(N'dbo.UsrQMSSetup', N'U') IS NULL
BEGIN
    CREATE TABLE [dbo].[UsrQMSSetup] (
        [CompanyID] [int] NOT NULL,
        [InspectionOrderNumberingID] [nvarchar](10) NOT NULL,
        [NCRNumberingID] [nvarchar](10) NOT NULL,
        [tstamp] [timestamp] NOT NULL,
        [CreatedByID] [uniqueidentifier] NOT NULL,
        [CreatedByScreenID] [char](8) NOT NULL,
        [CreatedDateTime] [datetime] NOT NULL,
        [LastModifiedByID] [uniqueidentifier] NOT NULL,
        [LastModifiedByScreenID] [char](8) NOT NULL,
        [LastModifiedDateTime] [datetime] NOT NULL,
        CONSTRAINT [UsrQMSSetup_PK] PRIMARY KEY CLUSTERED
        (
            [CompanyID] ASC
        )
    );
END

IF OBJECT_ID(N'dbo.QMSSetup', N'SN') IS NULL
    AND OBJECT_ID(N'dbo.QMSSetup', N'U') IS NULL
    AND OBJECT_ID(N'dbo.UsrQMSSetup', N'U') IS NOT NULL
    CREATE SYNONYM [dbo].[QMSSetup] FOR [dbo].[UsrQMSSetup];

-- InventoryItem usr columns (I.dac InventoryItemExt). Table already exists.

IF COL_LENGTH(N'dbo.InventoryItem', N'UsrQMSInspectionRequired') IS NULL
BEGIN
    ALTER TABLE [dbo].[InventoryItem] ADD
        [UsrQMSInspectionRequired] [bit] NOT NULL
        CONSTRAINT [DF_InventoryItem_UsrQMSInspectionRequired] DEFAULT ((0));
END

IF COL_LENGTH(N'dbo.InventoryItem', N'UsrQMSInspectionPlanID') IS NULL
BEGIN
    ALTER TABLE [dbo].[InventoryItem] ADD
        [UsrQMSInspectionPlanID] [nvarchar](30) NULL;
END

IF COL_LENGTH(N'dbo.InventoryItem', N'UsrMinShelfLifeDays') IS NULL
BEGIN
    ALTER TABLE [dbo].[InventoryItem] ADD
        [UsrMinShelfLifeDays] [int] NOT NULL
        CONSTRAINT [DF_InventoryItem_UsrMinShelfLifeDays] DEFAULT ((0));
END

-- I.lot: 26.x INLotSerialStatus has no LotStatus column.
IF COL_LENGTH(N'dbo.INLotSerialStatus', N'UsrQMSLotStatus') IS NULL
BEGIN
    ALTER TABLE [dbo].[INLotSerialStatus] ADD
        [UsrQMSLotStatus] [nvarchar](10) NULL;
END

-- 26.x live lot qty is INLotSerialStatusByCostCenter (INLotSerialStatus is a projection).
IF COL_LENGTH(N'dbo.INLotSerialStatusByCostCenter', N'UsrQMSLotStatus') IS NULL
BEGIN
    ALTER TABLE [dbo].[INLotSerialStatusByCostCenter] ADD
        [UsrQMSLotStatus] [nvarchar](10) NULL;
END
