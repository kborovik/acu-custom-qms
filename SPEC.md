# Lab5.QMS

## §G GOAL
Ship Acumatica xRP customization `Lab5.QMS`: cannot-pass lot gate + REST CoA ingest + GMP audit record for lot release.

## §C CONSTRAINTS
- Publisher `Lab5.QMS` (namespace, DLL, zip); not tenant-named
- Domain field-level DAC/graph/REST schema stays in `domain/ACUMATICA_QMS_EXTENSION_SPEC.md`; this file = SDD control
- Companion ingestion = `acu-google-qms`; tenant inventory/users = `acu-gitops-qms`; not implemented here
- Post-publish Role `Quality Manager` + QM `RolesInGraph` seed lives here; zip ! Role `UsersInRoles` `RolesInGraph`; `ACU_USER` ← Quality Manager e2e-only
- Acumatica Cloud xRP customization project; C# DACs/graphs/screens; endpoint `QMS/22.200.001`
- Regulatory: Health Canada GMP GUI-0001 / GUI-0158 + 21 CFR Part 11
- Shipped artifact `Lab5_QMS_Customization.zip`; custom tables `UsrQMS*`
- Screen `QM.10.10.00` Quality Preferences named in sitemap; setup DAC fields underspecified in domain spec → numbering sequences `QORD` `QNCR`

## §I INTERFACES
- pkg: `Lab5_QMS_Customization.zip` → `_project/ProjectMetadata.xml` 22.200.001 + `Lab5.QMS.dll` + Pages_QM + `CreateQMSTables.sql`; ! Role `UsersInRoles` `RolesInGraph`
- cmd: `lab5-qms` Click console script on installable `lab5-qms` → pack `Lab5_QMS_Customization.zip` + CustomizationApi publish + post-publish Role seed
- dac: `QMSInspectionPlan` `QMSInspectionPlanTest` `QMSInspectionOrder` `QMSInspectionOrderResult` `QMSNonConformance` + `InventoryItemExt` (`UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays`)
- graph: `QMSInspectionPlanMaint` `QMSInspectionOrderEntry` (`EvaluateResults` `ReleaseLotDecision`) `QMSNonConformanceEntry` (`CloseNCR` `DispositionRTV`) `POReceiptEntry_Extension` on `Release`
- screen: Quality Management workspace — `QM.10.10.00` prefs, `QM.20.10.00` plans, `QM.30.10.00` orders, `QM.30.20.00` NCR
- rest: `/entity/QMS/22.200.001/` — InspectionPlan GET; InspectionOrder GET PUT; NonConformance GET POST
- files: Acumatica `/files` attach CoA PDF + JSON on `QMSInspectionOrder.NoteID`
- lot: `INLotSerialStatus.LotStatus` in {`QC Hold`, `Released`, `Quarantine`}
- role: `Quality Manager` or ingestion service-account token for QC Hold → Released; post-publish seed Bootstrap Role `Quality Manager` + `RolesInGraph` Accessrights=4 QM101000 QM201000 QM301000 QM302000 for Administrator (CompanyID 1) and Quality Manager; `ACU_USER` ← Quality Manager e2e-only

## §V INVARIANTS
V1: cannot-pass-lot-gate — `UsrQMSInspectionRequired=true` on `POReceiptEntry.Release` → lot `LotStatus=QC Hold` (not BOM-allocatable) + draft `QMSInspectionOrder` (PlanID, Lot, Vendor, ReceiptNbr); lot ! Released until all required plan tests Pass
V2: rest-coa-ingest — ingestion engine GET `InspectionPlan` (`$expand=Tests`) then PUT `InspectionOrder` results + lab cert metadata; attach original CoA PDF + parsed JSON via `/files`
V3: gmp-audit-record — `QMSInspectionOrder` + attached CoA PDF/JSON is system of record for lot release; plan+order carry `CreatedByID` `CreatedDateTime` `LastModifiedByID` `LastModifiedDateTime`; evaluation complete stamps `EvaluatedByID` `EvaluationDateTime`; QC Hold → Released requires ingestion service-account token or authenticated user w/ `Quality Manager` role
V4: evaluate — each required plan test: numeric `MinValue` ≤ `ActualNumericValue` ≤ `MaxValue` (bound nullable); text contains required token; shelf-life `ExpiryDate` ≥ `ReceiptDate` + `UsrMinShelfLifeDays`; any Fail or missing required → `OverallEvaluation` Fail; all Pass → Pass
V5: pass-path — `OverallEvaluation` Pass → `LotStatus` Released + order Status Completed
V6: fail-path — `OverallEvaluation` Fail → `LotStatus` Quarantine + insert `QMSNonConformance` + halt allocation
V7: plan-bounds — `MinValue` and `MaxValue` both set → `MinValue` ≤ `MaxValue`; `PlanID` unique uppercase
V8: publisher-lab5 — namespace `Lab5.QMS`; assembly `Lab5.QMS.dll`; zip `Lab5_QMS_Customization.zip`; zip ! Role `UsersInRoles` `RolesInGraph`
V9: three-way-link — `POReceipt.ReceiptNbr` + `POReceiptLineSplit.LotSerialNbr` + `QMSInspectionOrder` stay consistent
V10: post-publish-qm-rights — after `Lab5.QMS` publish, Role `Quality Manager` exists + `RolesInGraph` Accessrights=4 on QM101000 QM201000 QM301000 QM302000 for Administrator (CompanyID 1) and Quality Manager; `gmake check` ! skip 403 on those screens; `ACU_USER` ← Quality Manager e2e-only

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
T12|x|pack `Lab5_QMS_Customization.zip`|V8,I.pkg
T13|x|seed post-publish Role `Quality Manager` + RolesInGraph Delete on QM* for Administrator and Quality Manager; attach Quality Manager to `ACU_USER` e2e-only; drop InspectionPlan 403 skip|V10,V8,I.role,I.pkg
T14|.|add Click console script `lab5-qms` pack+publish+post-publish Role seed|V10,V8,I.cmd,I.pkg

## §B BUGS
id|date|cause|fix
