import {
  PXScreen,
  PXView,
  PXActionState,
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
  graphType: "Lab5.QMS.QMSInspectionOrderEntry",
  primaryView: "Document",
  pageLoadBehavior: PXPageLoadBehavior.GoFirstRecord,
  hideFilesIndicator: false,
  hideNotesIndicator: false,
})
export class QM301000 extends PXScreen {
  EvaluateResults: PXActionState;
  ReleaseLotDecision: PXActionState;

  @viewInfo({ containerName: "Inspection Order" })
  Document = createSingle(QMSInspectionOrder);

  @viewInfo({ containerName: "Results" })
  Results = createCollection(QMSInspectionOrderResult);
}

export class QMSInspectionOrder extends PXView {
  InspectionOrderNbr: PXFieldState<PXFieldOptions.CommitChanges>;
  Status: PXFieldState;
  InventoryID: PXFieldState;
  LotSerialNbr: PXFieldState;
  VendorID: PXFieldState;
  @controlConfig({ allowEdit: true })
  ReceiptNbr: PXFieldState;
  PlanID: PXFieldState;
  TestingLabID: PXFieldState;
  LabCertificateNbr: PXFieldState;
  OverallEvaluation: PXFieldState;
  EvaluatedByID: PXFieldState<PXFieldOptions.Disabled>;
  EvaluationDateTime: PXFieldState<PXFieldOptions.Disabled>;
}

@gridConfig({
  preset: GridPreset.Details,
  allowInsert: true,
  allowDelete: true,
})
export class QMSInspectionOrderResult extends PXView {
  TestID: PXFieldState;
  TestMethod: PXFieldState;
  TargetSpec: PXFieldState;
  ActualNumericValue: PXFieldState;
  ActualTextValue: PXFieldState;
  Evaluation: PXFieldState;
  Notes: PXFieldState;
}
