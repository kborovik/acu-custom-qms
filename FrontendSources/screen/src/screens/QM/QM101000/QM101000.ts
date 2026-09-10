import {
  PXScreen,
  PXView,
  PXFieldState,
  createSingle,
  graphInfo,
  viewInfo,
  controlConfig,
} from "client-controls";

@graphInfo({
  graphType: "Lab5.QMS.QMSSetupMaint",
  primaryView: "Setup",
})
export class QM101000 extends PXScreen {
  @viewInfo({ containerName: "Quality Preferences" })
  Setup = createSingle(QMSSetup);
}

export class QMSSetup extends PXView {
  @controlConfig({ allowEdit: true })
  InspectionOrderNumberingID: PXFieldState;

  @controlConfig({ allowEdit: true })
  NCRNumberingID: PXFieldState;
}
