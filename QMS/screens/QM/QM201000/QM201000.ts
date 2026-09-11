import {
  PXScreen,
  PXView,
  PXFieldState,
  PXFieldOptions,
  createSingle,
  createCollection,
  graphInfo,
  viewInfo,
  gridConfig,
  controlConfig,
  GridPreset,
  PXPageLoadBehavior,
} from "client-controls";

@graphInfo({
  graphType: "Lab5.QMS.QMSInspectionPlanMaint",
  primaryView: "Document",
  pageLoadBehavior: PXPageLoadBehavior.GoFirstRecord,
})
export class QM201000 extends PXScreen {
  @viewInfo({ containerName: "Inspection Plan" })
  Document = createSingle(QMSInspectionPlan);

  @viewInfo({ containerName: "Inspection Tests" })
  Tests = createCollection(QMSInspectionPlanTest);
}

export class QMSInspectionPlan extends PXView {
  @controlConfig({ commitChanges: true })
  PlanID: PXFieldState<PXFieldOptions.CommitChanges>;
  Description: PXFieldState;
  InventoryID: PXFieldState;
  SamplingPlan: PXFieldState;
  Status: PXFieldState;
  EffectiveDate: PXFieldState;
}

@gridConfig({
  preset: GridPreset.Details,
  allowInsert: true,
  allowDelete: true,
})
export class QMSInspectionPlanTest extends PXView {
  LineNbr: PXFieldState;
  TestID: PXFieldState<PXFieldOptions.CommitChanges>;
  Description: PXFieldState;
  TestMethod: PXFieldState;
  TargetValue: PXFieldState;
  MinValue: PXFieldState;
  MaxValue: PXFieldState;
  UOM: PXFieldState;
  Criticality: PXFieldState;
}
