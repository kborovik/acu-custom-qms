import {
  PXScreen,
  PXView,
  PXActionState,
  PXFieldState,
  PXFieldOptions,
  createSingle,
  graphInfo,
  viewInfo,
  controlConfig,
  PXPageLoadBehavior,
} from "client-controls";

@graphInfo({
  graphType: "Lab5.QMS.QMSNonConformanceEntry",
  primaryView: "Document",
  pageLoadBehavior: PXPageLoadBehavior.GoFirstRecord,
})
export class QM302000 extends PXScreen {
  CloseNCR: PXActionState;
  DispositionRTV: PXActionState;

  @viewInfo({ containerName: "Non-Conformance" })
  Document = createSingle(QMSNonConformance);
}

export class QMSNonConformance extends PXView {
  NCRNbr: PXFieldState<PXFieldOptions.CommitChanges>;
  Status: PXFieldState;
  InspectionOrderNbr: PXFieldState;
  InventoryID: PXFieldState;
  LotSerialNbr: PXFieldState;
  VendorID: PXFieldState;
  @controlConfig({ allowEdit: true })
  ReceiptNbr: PXFieldState;
  Severity: PXFieldState;
  NonConformanceType: PXFieldState;
  RootCauseCategory: PXFieldState;
  AssignedQAOfficer: PXFieldState;
  InventoryHoldStatus: PXFieldState;
  ActionRequired: PXFieldState;

  @controlConfig({ rows: 3 })
  Description: PXFieldState;
}
