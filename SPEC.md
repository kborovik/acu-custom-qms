# Lab5.QMS

## §G GOAL
Ship Acumatica xRP customization `Lab5.QMS`: cannot-pass lot gate + REST CoA ingest + GMP audit record for lot release.

## §C CONSTRAINTS
- Publisher `Lab5.QMS` (namespace, DLL, zip); not tenant-named
- Domain field-level DAC/graph/REST schema stays in `README.md`; this file = SDD control
- Companion ingestion = `acu-google-qms`; tenant inventory/users = `acu-gitops-qms`; not implemented here
- Post-publish Role `Quality Manager` + QM `RolesInGraph` seed lives here; zip ! Role `UsersInRoles` `RolesInGraph`; `ACU_USER` ← Quality Manager e2e-only
- Acumatica Cloud xRP customization project; C# DACs/graphs/screens; endpoint `QMS/22.200.001`
- Regulatory: Health Canada GMP GUI-0001 / GUI-0158 + 21 CFR Part 11
- Shipped artifact `Lab5_QMS_Customization.zip`; custom tables `UsrQMS*`
- Screen `QM.10.10.00` Quality Preferences named in sitemap; setup DAC fields underspecified in README → numbering sequences `QORD` `QNCR`
- Released PATH `acu` via `uv tool install`; project ! `acumatica-cli` dep; Python ! `import acumatica_cli`; sibling in-dev checkout stays out of this env

## §I INTERFACES
- pkg: `Lab5_QMS_Customization.zip` → `_project/ProjectMetadata.xml` 22.200.001 + `_project/SiteMap.xml` (Inventory workspace QM101000 QM201000 QM301000 QM302000 QM401000; SelectedUI=D; ! QMS MUIWorkspace; ! QM000000) + `Lab5.QMS.dll` + Pattern B `PerTenantFile` zip members `screens/QM/<ScreenID>/` HTML+TS (repo `QMS/FrontendSources/screen/src/development/screens/QM/`) + Pattern A `PerTenantFile` `screens/IN/IN202500/extensions/IN202500_QMS.html|.ts` (repo `QMS/FrontendSources/screen/src/development/screens/IN/IN202500/extensions/`) + GenericInquiryScreen QM401000 (inspectable zip member; live GI = post-publish SQL seed) + `CreateQMSTables.sql` (repo `QMS/SQL/CreateQMSTables.sql`; zip `Scripts/CreateQMSTables.sql`) + File items `Pages/QM/*.aspx` (REST host; repo `QMS/Pages/QM/`); C# `QMS/Lab5.QMS/`; package XML `QMS/_project/`; zip ! File items for HTML+TS; zip ! `<Page>`; ! Role `UsersInRoles` `RolesInGraph`
- cmd: `acuqms` Click console script on installable `acuqms` (import pkg `acuqms`) → subcommands `build` `publish` `seed` `deploy`; no subcommand → Click help exit 0 (not deploy); `build` writes `Lab5_QMS_Customization.zip` (SSH compile `Lab5.QMS.dll` via `acuqms/dll.py` when C# stale); `deploy` build zip + CustomizationApi publish + post-publish Role seed + `UsrQMSSetup` (QORD QNCR) per company when missing; `publish`/`deploy` `--timeout` default 900s bounds CustomizationApi publishEnd poll only; `wait_published` default 600s after publishEnd (after `_ensure_qms_detail_mappings` + `_ensure_qm_aspx_pages` SHA-256 skip + recycle); import+publish always recycle before `wait_published` (nested maps already present still recycle); `_recycle_app_pool` `wait_rest` 120s not `wait_published`; InspectionPlan 500 OptimizedExport NRE after first recycle → recycle again then `wait_published`; `wait_published` emit start + poll heartbeat last GET kind (heartbeat ! completion 4-col schema); reuse session across polls; `ssh_run` ! `SSH_TIMEOUT`; wait timeout RuntimeError ! last InspectionPlan GET status or body kind; build/publish/seed/deploy emit per-step progress on stderr (step, target, result, elapsed); stdout stays path / status / `seeded`; skip already-published only when current tenant GET `/entity/QMS/22.200.001/InspectionPlan` 200 JSON array (empty OK); skip then seed then re-check live; after deploy GET `/entity` lists `QMS/22.200.001`; ! root `dll.py`; ! console `lab5-qms`; ! pkg `lab5_qms`
- cli: `acu` PATH (released `uv tool install`) → `acu config check` `acu config show` `acu tenant list`; ! `uv run acu`; ! `acu check` (destructive rebuild); Python ! `import acumatica_cli`
- dac: `QMSSetup` (`InspectionOrderNumberingID` `NCRNumberingID`) `QMSInspectionPlan` `QMSInspectionPlanTest` `QMSInspectionOrder` `QMSInspectionOrderResult` `QMSNonConformance` + `InventoryItemExt` (`UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays`)
- graph: `QMSSetupMaint` `QMSInspectionPlanMaint` `QMSInspectionOrderEntry` (`EvaluateResults` `ReleaseLotDecision`) `QMSNonConformanceEntry` (`CloseNCR` `DispositionRTV`) `POReceiptEntry_Extension` on `Release`; Kit Assembly IN307000 + BOM/issue graph extensions on allocate/issue
- screen: Inventory workspace only — `QM.10.10.00` Quality Preferences (Preferences), `QM.20.10.00` Inspection Plans (Profiles), `QM.30.10.00` Inspection Orders (Transactions), `QM.30.20.00` Non-Conformance Reports (Transactions), `QM.40.10.00` Quality Queue GI (Inquiries); ScreenIDs QM101000 QM201000 QM301000 QM302000 QM401000; Pattern B PXScreen HTML+TS four QM forms packed `PerTenantFile`; Pattern A IN202500_QMS Usr* fields packed `PerTenantFile`; SiteMap SelectedUI=D; ! QMS MUIWorkspace; ! QM000000; ! Configuration; REST host `Pages/QM/*.aspx` stubs; ScreenId URLs open Modern UI; Pattern B Tests/Results hide LineNbr; Test ID human key; REST LineNbr stay; QM301000 QM302000 ReceiptNbr DisplayName Purchase Receipt AllowEdit → PO302000; Order PlanID DisplayName Inspection Plan
- rest: `/entity/QMS/22.200.001/` — InspectionPlan GET PUT (`$expand=Tests`); InspectionOrder GET PUT; NonConformance GET POST; QMSSetup GET PUT (QM101000)
- stock: REST PUT/GET StockItem persist `UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays` on `InventoryItemExt` (extend Default or QMS entity); GitOps `config/qms/20-stock-item-qms.yaml`
- files: Acumatica `/files` attach CoA PDF + JSON on `QMSInspectionOrder.NoteID`
- lot: `INLotSerialStatusExt.UsrQMSLotStatus` in {`QC Hold`, `Released`, `Quarantine`}; 26.x `INLotSerialStatus` has no `LotStatus`
- role: `Quality Manager` or ingestion service-account token for QC Hold → Released; post-publish seed Bootstrap Role `Quality Manager` + `RolesInGraph` Accessrights=4 QM101000 QM201000 QM301000 QM302000 QM401000 for Administrator (CompanyID 1) and Quality Manager; `ACU_USER` ← Quality Manager e2e-only

## §V INVARIANTS
V1: cannot-pass-lot-gate — `UsrQMSInspectionRequired=true` on `POReceiptEntry.Release` → lot `UsrQMSLotStatus=QC Hold` (not BOM-allocatable per cannot-issue-unreleased-lot) + draft `QMSInspectionOrder` (PlanID, Lot, Vendor, ReceiptNbr); lot ! Released until all required plan tests Pass
V2: rest-coa-ingest — ingestion engine GET `InspectionPlan` (`$expand=Tests` returns test lines when `UsrQMSInspectionPlanTest` rows exist) then PUT `InspectionOrder` results + lab cert metadata; attach original CoA PDF + parsed JSON via `/files`
V3: gmp-audit-record — `QMSInspectionOrder` + attached CoA PDF/JSON is system of record for lot release; plan+order carry `CreatedByID` `CreatedDateTime` `LastModifiedByID` `LastModifiedDateTime`; evaluation complete stamps `EvaluatedByID` `EvaluationDateTime`; QC Hold → Released requires ingestion service-account token or authenticated user w/ `Quality Manager` role
V4: evaluate — each required plan test: numeric `MinValue` ≤ `ActualNumericValue` ≤ `MaxValue` (bound nullable); text contains required token; shelf-life `ExpiryDate` ≥ `ReceiptDate` + `UsrMinShelfLifeDays`; any Fail or missing required → `OverallEvaluation` Fail; all Pass → Pass
V5: pass-path — `OverallEvaluation` Pass → `UsrQMSLotStatus` Released + order Status Completed
V6: fail-path — `OverallEvaluation` Fail → `UsrQMSLotStatus` Quarantine + insert `QMSNonConformance` + halt allocation
V7: plan-bounds — `MinValue` and `MaxValue` both set → `MinValue` ≤ `MaxValue`; `PlanID` unique uppercase
V8: publisher-lab5 — namespace `Lab5.QMS`; assembly `Lab5.QMS.dll`; zip `Lab5_QMS_Customization.zip`; zip ! Role `UsersInRoles` `RolesInGraph`
V9: three-way-link — `POReceipt.ReceiptNbr` + `POReceiptLineSplit.LotSerialNbr` + `QMSInspectionOrder` stay consistent
V10: post-publish-qm-rights — after `Lab5.QMS` publish, Role `Quality Manager` exists + `RolesInGraph` Accessrights=4 on QM101000 QM201000 QM301000 QM302000 QM401000 for Administrator (CompanyID 1) and Quality Manager; `gmake e2e` ! skip 403 on those screens; `ACU_USER` ← Quality Manager e2e-only
V11: released-acu-cli — project ! declare `acumatica-cli` (`pyproject.toml` deps / `[tool.uv.sources]` / lock); live e2e + publish + dll SSH invoke PATH `acu` from `uv tool install`; ! `uv run acu`; Python ! `import acumatica_cli`
V12: inspection-plan-rest-write — PUT `/entity/QMS/22.200.001/InspectionPlan` w/ Tests → 200 create/update plan + test lines; GET `{PlanID}?$expand=Tests` returns those lines; GitOps `config/qms/10-inspection-plans.yaml` applies w/o 500
V13: stock-item-qms-rest — PUT StockItem persists `UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays` on `InventoryItem`; GET same contract returns the three fields; GitOps `config/qms/20-stock-item-qms.yaml` apply sets flags on all six PARTS items w/o SQL
V14: qms-setup-seed-rest — after `Lab5.QMS` publish, `UsrQMSSetup` row exists (QORD QNCR) per company when missing; `QMS/22.200.001` QMSSetup GET PUT mapped QM101000; GitOps PUT Quality Preferences w/o UI Save or SQL; PO receipt Release on tenant w/ no prior QM101000 Save → draft InspectionOrder (not 422 PXSetup empty)
V15: cannot-issue-unreleased-lot — Kit Assembly IN307000 + BOM/issue graphs refuse lots with `UsrQMSLotStatus` QC Hold or Quarantine; issue allowed only when Released
V16: inventory-hosted-qm — `_project/SiteMap.xml` assigns QM101000 QM201000 QM301000 QM302000 QM401000 to system Inventory workspace (subcats Preferences Profiles Transactions Transactions Inquiries); ! MUIWorkspace QMS; ! QM000000; ! Configuration membership; after `Lab5.QMS` publish, Inventory lists Quality Preferences Inspection Plans Inspection Orders Non-Conformance Reports Quality Queue; Search finds those five titles; workspace bar ! QMS tile; ScreenId URLs open Modern UI; Quality Queue GI `QM401000` row = Inspection Order still work (lot QC Hold or order ! Completed or related NCR ! Closed); one row per `inspectionOrderNbr` (`GIGroupBy`); drills `QM301000` order + `QM302000` NCR when present; GI ! Evaluate ReleaseLot CloseNCR DispositionRTV
V17: modern-ui-only — zip ships Pattern B HTML+TS four QM forms as `PerTenantFile` `screens/QM/<ScreenID>/` (repo `QMS/FrontendSources/screen/src/development/screens/QM/`; class name = ScreenID; graphType `Lab5.QMS.QMSSetupMaint` `QMSInspectionPlanMaint` `QMSInspectionOrderEntry` `QMSNonConformanceEntry`) + Pattern A `IN202500_QMS` `PerTenantFile` `screens/IN/IN202500/extensions/` (repo `QMS/FrontendSources/screen/src/development/screens/IN/IN202500/extensions/`) showing `UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays`; Pattern A TS `InventoryItem_QMS extends InventoryItem` (webpack `@extendsView`); zip ! `export class InventoryItem {`; Item.UsrQMS* bind FieldState (closes §B.11); publish copies to `customizationScreens/<tenant>/screens` + webpack `Scripts/Screens/<tenant>/<ScreenID>.html`; zip File items `Pages/QM/*.aspx` (REST graph host; repo `QMS/Pages/QM/`); zip ! File items for HTML+TS; zip ! `<Page>` items; SiteMap SelectedUI=D (! E Classic lock); ScreenId URLs open Modern UI; Quality tab ? `visible.bind` not `if.bind`; GitOps StockItem persist stays §V.13
V18: publish-skip-tenant-qms — `acuqms` publish skip `already published` only when current tenant GET `/entity/QMS/22.200.001/InspectionPlan` 200 JSON array (empty OK); 200 HTML or 200 error object or 401/404 ! live; CustomizationApi getPublished `Lab5.QMS` + GET `/entity` listing `QMS/22.200.001` ! sufficient (instance-wide leftover after tenant delete+create); skip then seed then re-check live — fail → import+publish+`wait_published`; after deploy GET `/entity` lists `QMS/22.200.001`
V19: wait-published-600s — `wait_published` default 600s; `publish_package` ! pass 120s; CLI `--timeout` bounds CustomizationApi publishEnd poll only; `_recycle_app_pool` `wait_rest` 120s not `wait_published`; `wait_published` emit start + poll heartbeat last GET kind; reuse session across polls; `ssh_run` ! `SSH_TIMEOUT`; wait timeout RuntimeError ! last GET status or body kind (HTML / error object / transport) (closes §B.9, §B.12)
V20: entitymapping-before-wait — `publish_package` after publishEnd: `_ensure_qms_detail_mappings` then `_ensure_qm_aspx_pages` (scp skip SHA-256 match) then recycle then `wait_published`; import+publish always recycle (nested maps already present still recycle); 26.101 publish ! nested Tests/Results EntityMapping; InspectionPlan GET 200 JSON array requires those rows + `Pages/QM/*.aspx` + pool recycle; aspx recopy after wait retriggers ASP.NET compile; `_recycle_app_pool` `wait_rest` GET `/entity` 200 ! QMS live; InspectionPlan 500 OptimizedExport NRE after that recycle → recycle again (bounded) then `wait_published` (closes §B.10, §B.12, §B.13, §B.15)
V21: py-shebang-exec — tracked `*.py` git mode 100755 iff first line starts `#!`; else 100644; `acuqms/*` `e2e/helper.py` `e2e/__init__.py` ! shebang
V22: qm-document-pager — QMSInspectionOrderEntry QMSInspectionPlanMaint QMSNonConformanceEntry Document PXSelect ! Where key Equal Current<key>; Next/Prev/First/Last land persisted sibling; Current-key filter only detail views (Results Tests) (closes §B.14)
V23: native-detail-identity — Pattern B QM201000 Tests + QM301000 Results hide LineNbr (native PO301000 analog); Test ID human-key first; DAC LineNbr `PXUIField Visible=false`; REST `QMS/22.200.001` Tests/Results LineNbr stay; empty `<qp-grid>` dumps TS view fields so view class ! LineNbr; Classic ASPX ! `PXGridColumn DataField="LineNbr"`
V24: receipt-doc-link — QM301000 QM302000 ReceiptNbr DisplayName Purchase Receipt + AllowEdit opens PO Receipt PO302000; QMSInspectionOrder.PlanID DisplayName Inspection Plan (selector stay, ! require AllowEdit); QMSInspectionPlan.PlanID stay Plan ID; Stock Item UsrQMSInspectionPlanID already Inspection Plan; REST field names ReceiptNbr PlanID stay

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
T14|x|add Click console script `lab5-qms` pack+publish+post-publish Role seed|V10,V8,I.cmd,I.pkg
T15|x|naked `lab5-qms` (no subcommand) emit Click help exit 0; not invoke deploy|I.cmd
T16|x|deploy/publish/seed emit per-step progress on stderr: pack zip, drain in-flight publish, digest skip or import, publishBegin, poll publishEnd, wait `QMS/22.200.001`, seed Role, seed RolesInGraph|V10,I.cmd
T17|x|drop `acumatica-cli` from `pyproject.toml` deps + `[tool.uv.sources]`; relock|V11
T18|x|swap `lab5_qms` `dll.py` `e2e` `import acumatica_cli` → PATH `acu` CLI|V11,I.cli
T19|x|preflight Makefile AGENTS.md README: `acu config check` not `uv run acu`; `uv tool install` released `acu`|V11,I.cli
T20|x|map InspectionPlan PUT + Tests detail on `QMS/22.200.001`; PUT w/ Tests → 200 create/update; GET `$expand=Tests` returns test lines|V12,V2,I.rest
T21|x|e2e drop InspectionPlan PUT-unavailable skip; prove PUT 200 + GET expand Tests; GitOps six-plan PUT shape no 500|V12,V2,I.rest,T20
T22|x|map `UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays` on REST StockItem (extend Default or QMS entity writing `InventoryItemExt`)|V13,I.stock,I.dac
T23|x|e2e prove PARTS StockItem PUT persist + GET roundtrip; GitOps six-item `config/qms/20-stock-item-qms.yaml` apply no SQL|V13,I.stock,T22
T24|x|map QMSSetup GET PUT on `QMS/22.200.001` (QM101000)|V14,I.rest,I.dac,I.graph
T25|x|post-publish seed insert `UsrQMSSetup` (QORD QNCR) per company when missing|V14,I.cmd
T26|x|e2e prove QMSSetup GET PUT; GitOps PUT Quality Preferences no UI/SQL; PO receipt Release no prior QM101000 Save → draft InspectionOrder not 422|V14,I.rest,T24,T25
T27|x|add Kit Assembly IN307000 + BOM/issue graph extensions: refuse `UsrQMSLotStatus` QC Hold or Quarantine; allow issue only when Released|V15,V1,I.lot,I.graph
T28|x|unit-test Kit Assembly IN307000 refuse QC Hold / Quarantine; live e2e ! kit|V15,I.lot,T27
T29|x|assign QM* Site Map rows to Quality Management workspace in `_project/SiteMap.xml` (not SelectedUI=E folder-only empty Workspaces)|V16,I.screen,I.pkg
T30|x|e2e prove after publish: modern UI workspace bar or More Items shows Quality Management; Search finds Quality Preferences Inspection Plans Inspection Orders Non-Conformance Reports; Site Map Workspaces populated `QM.00.00.00` `QM.10.10.00` `QM.20.10.00` `QM.30.10.00` `QM.30.20.00`; ScreenId URLs keep working|V16,I.screen,T29
T31|x|patch `_project/SiteMap.xml` Inventory workspace QM101000 QM201000 QM301000 QM302000 QM401000 (Preferences Profiles Transactions Transactions Inquiries); drop MUIWorkspace QMS + QM000000; ! Configuration membership|V16,I.screen,I.pkg
T32|x|add Pattern B HTML+TS four QM forms `QMS/screens/QM/<ScreenID>/`; class name = ScreenID; graphType `Lab5.QMS.QMSSetupMaint` `QMSInspectionPlanMaint` `QMSInspectionOrderEntry` `QMSNonConformanceEntry`; Evaluate ReleaseLot CloseNCR DispositionRTV Notes Files stay|V17,I.screen,I.pkg
T33|x|add Pattern A `IN202500_QMS` HTML+TS `QMS/screens/IN/IN202500/extensions/`; show `UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays`; Quality tab ? `visible.bind` not `if.bind`|V17,I.stock,I.dac
T34|x|add GenericInquiryScreen `QM401000` Quality Queue + sitemap Inquiries; row = Inspection Order still work (lot QC Hold or order ! Completed or related NCR ! Closed); one row per order (`GIGroupBy` `Order.inspectionOrderNbr`); drills QM301000 order + QM302000 NCR; GI ! Evaluate ReleaseLot CloseNCR DispositionRTV|V16,V1,V6,I.screen,I.pkg
T35|x|ship File items `Pages/QM/*.aspx` REST graph host (repo `QMS/Pages/QM/`); zip ! `<Page>` items|V17,I.pkg
T36|x|seed RolesInGraph Accessrights=4 `QM401000` for Administrator and Quality Manager|V10,I.role
T37|x|e2e prove after publish: Inventory lists Quality Preferences Inspection Plans Inspection Orders Non-Conformance Reports Quality Queue; Search finds five titles; workspace bar ! QMS tile; Configuration ! list those screens; ScreenId URLs QM101000 QM201000 QM301000 QM302000 open Modern; Evaluate ReleaseLot CloseNCR DispositionRTV Notes Files work; Quality Queue lists work rows + drills (one row per order); Stock Items IN202500 shows three Usr* fields; Site Map ! QM000000; zip GenericInquiryScreen QM401000 + Pattern B + Pattern A + File items Pages/QM ASPX + ! `<Page>`|V16,V17,V10,I.screen,I.stock,T31,T32,T33,T34,T35,T36
T38|x|drop e2e/test_kit_assembly_lot_gate.py; live e2e inventory-only|V16,T28,T37
T39|x|pack Pattern B/A as `PerTenantFile` `screens/QM|IN/...` (not File → src/screens); SiteMap SelectedUI=D; drop leftover src/screens File copies before publish; seed SelectedUI D; e2e `Scripts/Screens/<tenant>/QM*.html` + SelectedUI ! E|V17,I.pkg,I.screen
T40|x|skip already-published only when current tenant GET `/entity/QMS/22.200.001/InspectionPlan` 200 (empty OK); leftover getPublished or GET /entity listing ! skip; tenant 404 → import+publish+wait_published|V18,I.cmd
T41|x|tighten `qms_endpoint_live` 200 JSON array; skip then seed then re-check live; unit 200 HTML / error dict / 401 ! live; e2e after deploy GET `/entity` lists QMS + InspectionPlan JSON array on skip path|V18,B8,I.cmd
T42|x|drop `wait_published(timeout=120.0)` in `publish_package` + `_recycle_app_pool`; use 600s default; unit assert wait timeout 600 not 120; timeout error last GET status/body kind|V19,I.cmd,B9
T43|x|seed EntityMapping Tests/Results before wait_published in publish_package; recycle if inserted; unit assert call order; GET 200 after maps|V20,I.cmd,B10
T44|x|fix Pattern A IN202500_QMS.ts `InventoryItem_QMS extends InventoryItem`; unit assert ! `export class InventoryItem {`; e2e published TS extends + webpack `@extendsView`; Stock Items New Record Item.UsrQMS* bind FieldState|V17,I.stock,T33,B11
T45|x|move customization sources under `QMS/` (C# `QMS/Lab5.QMS/`; Pages `QMS/Pages/QM/`; screens `QMS/screens/`; `_project`; SQL `QMS/SQL/CreateQMSTables.sql`); zip members unchanged; Python packer/tests stay at root|V8,V17,I.pkg
T46|x|sweep tracked `*.py` git mode 100755 iff shebang else 100644 (scope: `^#!` in `*.py`); unit-test pairing|V21
T47|x|swap pkg+console `lab5-qms`/`lab5_qms` → `acuqms`; Click `pack` → `build`; move `dll.py` → `acuqms/dll.py` (drop shebang); Makefile AGENTS README tests follow|I.cmd,V18,V21
T48|x|move Pattern B/A sources `QMS/screens/` → `QMS/FrontendSources/screen/src/development/screens/`; packer reads that tree; zip members `screens/QM|IN/...` unchanged|V17,I.pkg,T45
T49|x|sweep tests Path-literal `QMS/FrontendSources/screen/src/development/screens` → import `FRONTEND_SCREENS_REL` from `acuqms.paths` (scope: `tests/**/*.py`)|V17,I.pkg,T48
T50|x|wait_published emit start + poll last-GET heartbeat; recycle wait_rest 120s; aspx SHA-256 skip before wait; ssh_run SSH_TIMEOUT; reuse wait session|V19,V20,I.cmd,B12
T51|x|recycle after import+publish before wait_published even when nested maps already present|V20,I.cmd,B13
T52|x|fix QMSInspectionOrderEntry QMSInspectionPlanMaint QMSNonConformanceEntry Document PXSelect drop Current-key Where; Next/Prev land sibling; unit assert Document ! Equal Current; e2e QM301000 Next from named order lands next nbr|V22,B14,I.graph,I.screen
T53|x|hide LineNbr on QM201000 Tests + QM301000 Results (TS view ! LineNbr, ASPX ! PXGridColumn LineNbr, DAC Visible=false); REST LineNbr stay; unit GRID_FIELDS drop LineNbr + assert TS+ASPX ! LineNbr; e2e published TS ! LineNbr field|V23,I.screen
T54|x|after aspx+recycle, InspectionPlan 500 OptimizedExport NRE → recycle again then wait_published; GET /entity 200 ! QMS live; unit assert second recycle on NRE; e2e aspx-hash-mismatch publish → InspectionPlan 200 w/o manual recycle|V20,I.cmd,B15
T55|x|QM301000 QM302000 ReceiptNbr AllowEdit → PO302000; DisplayName Purchase Receipt; Order PlanID DisplayName Inspection Plan; Plan ! require AllowEdit; unit DAC DisplayName + ASPX AllowEdit + TS @controlConfig allowEdit ReceiptNbr; REST names stay|V24,I.screen

## §B BUGS
id|date|cause|fix
B1|2026-09-07|InspectionPlan mapped GET-only; Tests expand empty despite `UsrQMSInspectionPlanTest` rows; PUT 500|V12
B2|2026-09-07|Default StockItem PUT ignores UsrQMS* InventoryItemExt; SQL stays 0/NULL|V13
B3|2026-09-08|publish leaves UsrQMSSetup empty; QMSSetup not on REST; PO receipt Release 422 PXSetup|V14
B4|2026-09-08|PO receipt writes `UsrQMSLotStatus` QC Hold; Kit Assembly / IN issue graphs unread so QC Hold lots stay BOM-allocatable|V15
B5|2026-09-08|SiteMap.xml classic folder QM000000 SelectedUI=E; Workspaces empty → modern UI no tile no Search|V16
B6|2026-09-10|Pattern B packed as File → src/screens; publish skipped customizationScreens webpack; QM301000 SelectedUI=E → Classic ASPX|V17
B7|2026-09-10|digest skip treats instance-wide getPublished + GET /entity QMS listing as live tenant contract|V18
B8|2026-09-10|`qms_endpoint_live` status 200 only; skip then seed no re-check; leftover 200 then tenant 404|V18
B9|2026-09-11|wait_published callers hardcode 120s; CLI --timeout covers publishEnd only|V19
B10|2026-09-11|wait_published after publishEnd before EntityMapping seed; 26.101 ! nested Tests/Results maps; InspectionPlan GET 500|V20
B11|2026-09-11|Pattern A TS redeclares InventoryItem; webpack ! @extendsView; Item.UsrQMS* FieldState bind fail|V17
B12|2026-09-11|wait_published silent until finally; recycle nests wait_published; aspx seed after wait; ssh_run timeout None|V19,V20
B13|2026-09-11|recycle only if maps inserted; import+publish leaves QM GET 500 OptimizedExport NRE until pool recycle|V20
B14|2026-09-11|QM document Document PXSelect Current-key filter → Next Insert empty not sibling|V22
B15|2026-09-12|one recycle after aspx recopy; wait_rest GET /entity 200; wait_published polls InspectionPlan 500 OptimizedExport NRE until second recycle|V20
