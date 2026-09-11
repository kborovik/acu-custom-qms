import {
  PXFieldState,
  PXFieldOptions,
  controlConfig,
} from "client-controls";
import { IN202500, InventoryItem } from "src/screens/IN/IN202500/IN202500";

export interface IN202500_QMS extends IN202500 {}
export class IN202500_QMS {}

export interface InventoryItem_QMS extends InventoryItem {}
export class InventoryItem_QMS {
  @controlConfig({ commitChanges: true })
  UsrQMSInspectionRequired: PXFieldState<PXFieldOptions.CommitChanges>;

  @controlConfig({ allowEdit: true })
  UsrQMSInspectionPlanID: PXFieldState;

  @controlConfig({})
  UsrMinShelfLifeDays: PXFieldState;
}
