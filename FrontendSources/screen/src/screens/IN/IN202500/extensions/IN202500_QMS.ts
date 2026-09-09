import {
  PXView,
  PXFieldState,
  PXFieldOptions,
  controlConfig,
} from "client-controls";
import { IN202500 } from "../IN202500";

export interface IN202500_QMS extends IN202500 {}
export class IN202500_QMS {}

export class InventoryItemExtension extends PXView {
  @controlConfig({ commitChanges: true })
  UsrQMSInspectionRequired: PXFieldState<PXFieldOptions.CommitChanges>;

  @controlConfig({ allowEdit: true })
  UsrQMSInspectionPlanID: PXFieldState;

  UsrMinShelfLifeDays: PXFieldState;
}
