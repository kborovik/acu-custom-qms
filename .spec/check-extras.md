# check-extras — §V body overflow

/sdd:condense-extracted §V row bodies for token-budget management. Consulted verbatim by /sdd:check sub-agents via RECIPE_EXCERPT. Row ordering: ascending §V id.

## §V16 inventory-hosted-qm

V16: inventory-hosted-qm — `_project/SiteMap.xml` assigns QM101000 QM201000 QM301000 QM302000 QM401000 to system Inventory workspace (subcats Preferences Profiles Transactions Transactions Inquiries); ! MUIWorkspace QMS; ! QM000000; ! Configuration membership; after `Lab5.QMS` publish, Inventory lists Quality Preferences Inspection Plans Inspection Orders Non-Conformance Reports Quality Queue; Search finds those five titles; workspace bar ! QMS tile; ScreenId URLs open Modern UI; Quality Queue GI `QM401000` row = Inspection Order still work (lot QC Hold or order ! Completed or related NCR ! Closed); one row per `inspectionOrderNbr` (`GIGroupBy`); drills `QM301000` order + `QM302000` NCR when present; GI ! Evaluate ReleaseLot CloseNCR DispositionRTV

## §V17 modern-ui-only

V17: modern-ui-only — zip ships Pattern B HTML+TS four QM forms as `PerTenantFile` `screens/QM/<ScreenID>/` (repo `QMS/FrontendSources/screen/src/development/screens/QM/`; class name = ScreenID; graphType `Lab5.QMS.QMSSetupMaint` `QMSInspectionPlanMaint` `QMSInspectionOrderEntry` `QMSNonConformanceEntry`) + Pattern A `IN202500_QMS` `PerTenantFile` `screens/IN/IN202500/extensions/` (repo `QMS/FrontendSources/screen/src/development/screens/IN/IN202500/extensions/`) showing `UsrQMSInspectionRequired` `UsrQMSInspectionPlanID` `UsrMinShelfLifeDays`; Pattern A TS `InventoryItem_QMS extends InventoryItem` (webpack `@extendsView`); zip ! `export class InventoryItem {`; Item.UsrQMS* bind FieldState (closes §B.11); publish copies to `customizationScreens/<tenant>/screens` + webpack `Scripts/Screens/<tenant>/<ScreenID>.html`; zip File items `Pages/QM/*.aspx` (REST graph host; repo `QMS/Pages/QM/`); zip ! File items for HTML+TS; zip ! `<Page>` items; SiteMap SelectedUI=D (! E Classic lock); ScreenId URLs open Modern UI; Quality tab ? `visible.bind` not `if.bind`; GitOps StockItem persist stays §V.13

## §V18 publish-skip-tenant-qms

V18: publish-skip-tenant-qms — `acuqms` publish skip `already published` only when current tenant GET `/entity/QMS/22.200.001/InspectionPlan` 200 JSON array (empty OK); 200 HTML or 200 error object or 401/404 ! live; CustomizationApi getPublished `Lab5.QMS` + GET `/entity` listing `QMS/22.200.001` ! sufficient (instance-wide leftover after tenant delete+create); skip then seed then re-check live — fail → import+publish+`wait_published`; after deploy GET `/entity` lists `QMS/22.200.001`

## §V19 wait-published-600s

V19: wait-published-600s — `wait_published` default 600s; `publish_package` ! pass 120s; CLI `--timeout` bounds CustomizationApi publishEnd poll only; `_recycle_app_pool` `wait_rest` 120s not `wait_published`; `wait_published` emit start + poll heartbeat last GET kind; reuse session across polls; `ssh_run` ! `SSH_TIMEOUT`; wait timeout RuntimeError ! last GET status or body kind (HTML / error object / transport) (closes §B.9, §B.12)

## §V20 entitymapping-before-wait

V20: entitymapping-before-wait — `publish_package` after publishEnd: `_ensure_qms_detail_mappings` then `_ensure_qm_aspx_pages` (scp skip SHA-256 match) then recycle then `wait_published`; import+publish always recycle (nested maps already present still recycle); 26.101 publish ! nested Tests/Results EntityMapping; InspectionPlan GET 200 JSON array requires those rows + `Pages/QM/*.aspx` + pool recycle; aspx recopy after wait retriggers ASP.NET compile; `_recycle_app_pool` `wait_rest` GET `/entity` 200 ! QMS live; InspectionPlan 500 OptimizedExport NRE after that recycle → recycle again (bounded) then `wait_published` (closes §B.10, §B.12, §B.13, §B.15)

## §V26 unpublish-lab5-only

V26: unpublish-lab5-only — `acuqms unpublish` unpublishes Lab5.QMS only (AcuBootstrap stays); `ACU_SSH` set → drop `Pages/QM` + File-item `FrontendSources/screen/src/screens/QM` + `IN202500_QMS.*` + tenant `customizationScreens/<tenant>` + tenant `Scripts/Screens/<tenant>/QM*` + restore OOTB `Scripts/Screens` HTML (IN202500 GenericInquiry Dashboard ReportScreen ReportViewer PivotTable HierarchicalGrid ExternalResource) to site vendor from IN202000 + oldest bundle; ! `npm run build` `--env production` (partial production webpack rewrites GenericInquiry TIME_STAMP/vendor → Stock Items GI IN2025PL blank) (closes §B.16); ! Windows state-cache wipe; ! drop CNBN stock; no-SSH → CustomizationApi unpublish only (document); after unpublish getPublished ! Lab5.QMS + GET `/entity` ! `QMS/22.200.001` + InspectionPlan ! 200 JSON array; subsequent `acuqms deploy` imports (not digest-skip)

## §V27 pkg-description-version

V27: pkg-description-version — SM204505 + zip `project.xml` Description starts `Lab5.QMS {ver}`; `{ver}` = pyproject X.Y.Z iff HEAD exact tag `v{X.Y.Z}` + working tree clean; else `{X.Y.Z}-dev`; then `QMS customization 22.200.001; assembly Lab5.QMS.dll; zip Lab5_QMS_Customization.zip [sha256:{member digest}]`; CustomizationApi `projectDescription` = that string; publish skip `published_description` == `package_description`; pack stamps zip `project.xml`; committed `_project/ProjectMetadata.xml` ! live `{ver}`; pack ! GitHub API
