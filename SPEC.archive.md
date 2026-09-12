# SPEC.archive — archived rows

## §T TASKS

id|status|task|cites
T1|x|init customization project `Lab5.QMS` + `UsrQMS*` DDL|V8,I.pkg
T2|x|add `InventoryItemExt` usr fields|V1,I.dac
T3|x|add inspection plan DACs + `QMSInspectionPlanMaint` + `QM.20.10.00`|V7,I.dac,I.graph,I.screen
T4|x|add inspection order DACs + `QMSInspectionOrderEntry` + `QM.30.10.00` + `EvaluateResults`|V4,I.dac,I.graph,I.screen
T5|x|add NCR DAC + `QMSNonConformanceEntry` + `QM.30.20.00`|V6,I.dac,I.graph,I.screen
T6|x|add `POReceiptEntry_Extension` Release: QC Hold + draft order|V1,V9,I.graph
T7|x|add `ReleaseLotDecision` pass/fail lot flip + NCR auto-create|V5,V6,V9,I.lot
T8|x|register REST `QMS/22.200.001` InspectionPlan GET, InspectionOrder GET/PUT, NonConformance GET/POST|V2,I.rest
T9|x|attach CoA PDF + JSON via `/files` on InspectionOrder `NoteID`|V2,V3,I.files
T10|x|stamp audit fields + gate QC Hold→Released on service-account token or `Quality Manager`|V3,I.role
T11|x|add `QMSSetupMaint` `QM.10.10.00` numbering `QORD` `QNCR`|I.screen

## §B BUGS

id|date|cause|fix
