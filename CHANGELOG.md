# Changelog

## Unreleased

## [v0.5.2] - 2026-09-10

### Fixed

- **Publish skip (V18 / B7):** `lab5-qms` publish skips `already published`
  only when the current tenant `GET /entity/QMS/22.200.001/InspectionPlan`
  returns 200 (empty list OK). CustomizationApi `getPublished` listing
  `Lab5.QMS` plus `GET /entity` listing `QMS/22.200.001` is instance-wide
  leftover after tenant delete+create, so a new tenant would skip import.
  Missing endpoint now imports, publishes, and waits for InspectionPlan
  200.

## [v0.5.1] - 2026-09-10

### Fixed

- **Modern UI compile (V17 / B6):** Pattern B/A HTML+TS now pack as
  `PerTenantFile` (`screens/QM/<ScreenID>/`, `screens/IN/IN202500/extensions/`)
  so publish copies them to `customizationScreens/<tenant>` and webpack-emits
  `Scripts/Screens/<tenant>/<ScreenID>.html`. Ordinary `File` items into
  `FrontendSources/screen/src/screens` skipped that pipeline, so Inspection
  Orders stayed Classic ASPX. SiteMap `SelectedUI=D`; post-publish seed
  clears a Classic lock (`E`) and drops leftover src/screens copies.
  Pattern A imports `src/screens/IN/IN202500/IN202500` (relative `../IN202500`
  404s under customizationScreens). Publish sets the AcumaticaERP app-pool
  `NO_COLOR` (not machine-wide env) so webpack progress ANSI does not crash
  `CstWebsiteStorage.SaveStatus`. Pool recycle and leftover cleanup run
  *before* the CustomizationApi session; digest-skip also requires tenant
  `Scripts/Screens/<tenant>/QM*.html` so a failed publishBegin after import
  cannot leave webpack unrun.
- **InspectionPlan PUT e2e:** skip re-copy of `Pages/QM/*.aspx` when SHA-256
  matches (a new write time retriggers ASP.NET compile and PUT 500s
  `The view  doesn't exist`). Skipped DockLot no longer seeds in setUpClass.

## [v0.5.0] - 2026-09-10

### Added

- **`gmake deploy`:** pack `Lab5_QMS_Customization.zip`, publish via
  CustomizationApi, and seed Role / `RolesInGraph` / `UsrQMSSetup`. No
  live e2e — that stays `gmake e2e`.
- **Quality Queue GI (V16):** `QM401000` Generic Inquiry of Inspection
  Orders still work (lot QC Hold, order not Completed, or related NCR
  not Closed). One row per order; drills to Inspection Orders and NCR.
  Zip ships `_project/GenericInquiryScreen_QM401000.xml`.
- **Modern UI Pattern B / A (V17):** zip ships PXScreen HTML+TS for
  Quality Preferences, Inspection Plans, Inspection Orders, and
  Non-Conformance Reports, plus `IN202500_QMS` extensions so Stock Items
  shows `UsrQMSInspectionRequired`, `UsrQMSInspectionPlanID`, and
  `UsrMinShelfLifeDays`. REST host `Pages/QM/*.aspx` File items remain.

### Changed

- **Inventory-hosted QM (V16):** `_project/SiteMap.xml` assigns
  QM101000 / QM201000 / QM301000 / QM302000 / QM401000 to the system
  Inventory workspace (Preferences, Profiles, Transactions, Inquiries).
  Drops the QMS workspace tile and `QM000000`. After publish, Inventory
  lists those five screens; Search finds the titles; ScreenId URLs open
  Modern UI.
- **Recipes:** `gmake test` renamed to `gmake check` (ruff format, ruff
  lint, unit tests; no tenant). `gmake check` renamed to `gmake e2e`
  (`gmake check` + `acu config check` + live e2e). Matches acumatica-cli.
- **`gmake build`:** renamed from `gmake pack`. Still runs
  `lab5-qms pack`.
- **Pack compiles `Lab5.QMS.dll` when C# changes:** `lab5-qms pack` /
  `publish` / `deploy`, `gmake build` / `deploy` / `e2e` / `release`
  rebuild the assembly on the ERP VM when `src/Lab5.QMS` sources (or the
  compiler) change. Dropped `gmake dll` — compile is a dependency of
  those paths, not a recipe.
- **License:** relicense from PolyForm Noncommercial 1.0.0 to Apache-2.0.

### Fixed

- **Publish digest:** skip/import hashes every zip member (name +
  bytes), not only `project.xml` and `Bin/Lab5.QMS.dll`. An ASPX or SQL
  change republishes instead of leaving the tenant on old pages.

## [v0.4.0] - 2026-09-08

### Added

- **QMSSetup seed + REST (V14):** after `Lab5.QMS` publish, seed inserts
  `UsrQMSSetup` (QORD / QNCR) per company when missing. `QMS/22.200.001`
  maps QMSSetup GET/PUT on Quality Preferences (`QM101000`). GitOps can
  PUT preferences without a UI Save or SQL; PO receipt Release on a tenant
  with no prior QM101000 Save creates a draft InspectionOrder (not 422
  PXSetup empty).
- **Cannot-issue unreleased lot (V15):** Kit Assembly IN307000 and BOM/
  issue graph extensions refuse lots with `UsrQMSLotStatus` QC Hold or
  Quarantine. Issue is allowed only when Released.

### Fixed

- **Modern Quality Management workspace (V16):** `_project/SiteMap.xml`
  assigns QM* screens to the Quality Management workspace (not a classic
  SelectedUI=E folder with empty Workspaces). After publish, modern UI
  shows the workspace tile / More Items entry and Search finds Quality
  Preferences, Inspection Plans, Inspection Orders, and Non-Conformance
  Reports. ScreenId URLs keep working.

## [v0.3.0] - 2026-09-07

### Fixed

- **StockItem REST usr fields (V13):** `QMS/22.200.001` maps `StockItem` on
  Stock Items (`IN202500`) so PUT persists `UsrQMSInspectionRequired`,
  `UsrQMSInspectionPlanID`, and `UsrMinShelfLifeDays` on `InventoryItem`.
  GET of the same contract returns the three fields. Default `StockItem`
  still ignores UsrQMS* (B2).
- **InspectionPlan REST write (V12):** PUT `/entity/QMS/22.200.001/InspectionPlan`
  with Tests creates or updates a plan. GET `{PlanID}?$expand=Tests` returns
  test lines. Persist DACs bind to `UsrQMS*` via `[PXTableName]` because
  SQL synonyms are not in the PX schema cache (PUT 500
  `QMSInspectionPlan` does not exist). Detail field maps nest under the
  parent `Tests` / `Results` Mapping (`Detail` has Fields only). Post-publish
  seed writes `EntityMapping` `E/{parent}/{collectionField}/{detail}/{field}`
  rows so `$expand=Tests` returns lines. LineNbr re-PUT upserts existing
  test/result rows.

## [v0.2.0] - 2026-09-06

### Added

- **README:** sequence diagram under Quality workflow (receipt gate,
  CoA ingest, evaluate, lot decision), colored with lab5.ca brand
  (green, blue, yellow, red). Vertex AI is labeled **GCP AI Agent**;
  the receiving dock sends CoA PDF documents to that agent. Actors:
  Receiving Dock, Acumatica ERP, Quality Manager, GCP AI Agent. Drop
  the Business workflow object-path flowchart.
- **`lab5-qms` CLI:** Click console script on the installable `lab5-qms`
  package. Subcommands: `pack`, `publish`, `seed`, `deploy`. No
  subcommand prints Click help and exits 0 (does not deploy).
  `lab5-qms deploy` packs `Lab5_QMS_Customization.zip`, publishes via
  CustomizationApi, and seeds post-publish Role `Quality Manager` plus
  `RolesInGraph` Delete on the QM screens. Zip still excludes Role /
  UsersInRoles / RolesInGraph. `ACU_USER` role attach stays e2e-only.
- **Post-publish QM rights:** after `Lab5.QMS` publish, seed Role
  `Quality Manager` and `RolesInGraph` Delete (`Accessrights=4`) on
  `QM101000` / `QM201000` / `QM301000` / `QM302000` for Administrator
  (CompanyID 1) and Quality Manager. `gmake check` attaches Quality
  Manager to `ACU_USER` and no longer skips InspectionPlan 403.
- **`gmake dll`:** compile `Lab5.QMS.dll` on the ERP VM over SSH (site)
  Roslyn `csc` against `PX.Data` / `PX.Objects` / `PX.Common` /
  `PX.Common.Std`) and copy it to `src/Lab5.QMS/bin/Release` for
  `gmake pack`. The csproj now HintPaths those assemblies at
  `$(AcumaticaDir)\Bin` (default `C:\Acumatica\AcumaticaERP`).
  `gmake pack` depends on `dll`; `check` / `release` compile that path
  when it is missing.
- **`gmake clean`:** remove `Lab5.QMS.dll`, `obj/`, the pack zip,
  `__pycache__`, and other temp artifacts. Leaves `.venv` and `.env`.

### Changed

- **README:** Quality inspection workflow fills participant boxes:
  Acumatica ERP blue, Quality Manager green, GCP AI Agent red.
- **README:** fold the QMS extension specification into README (purpose,
  business workflow, entities, REST, screens, GMP). Remove
  `domain/ACUMATICA_QMS_EXTENSION_SPEC.md`.

- **Project deps:** drop `acumatica-cli` from `pyproject.toml` and
  `[tool.uv.sources]`; relock. Released PATH `acu` is not a project
  dependency. `lab5-qms` publish, `dll.py`, and e2e invoke PATH `acu`
  (`acu config show`, `acu tenant list`) plus a local httpx REST
  session. Python does not `import acumatica_cli`.
- **httpx:** direct project dependency for CustomizationApi / contract
  REST after dropping the CLI package.
- **Preflight:** `gmake check` / Makefile / AGENTS.md / README call
  PATH `acu config check`. Install with `uv tool install acumatica-cli`.
  Do not launch acu through uv.
- **`lab5-qms` progress:** `pack`, `publish`, `seed`, and `deploy` emit
  per-step progress on stderr (step, target, result, elapsed). Stdout
  stays the zip path, publish status, or `seeded`.
- **26.x lot status + roles:** `INLotSerialStatus` has no `LotStatus`
  field — persist `UsrQMSLotStatus`. QC Hold → Released reads roles via
  `PXAccess.GetRoles` (`GetUserRoles` is gone).

### Fixed

- **QM selector fields:** `EvaluatedByID` and `AssignedQAOfficer` now have
  `PXSelector` so InspectionOrder and NonConformance REST lists do not 500
  after rights are granted.
- **`gmake check` hang:** e2e HTTP default 30s (publish loop still 600s),
  `acu` subprocess 60s, sqlcmd-over-ssh 30s, bounded InspectionOrder 202
  poll 60s, unbuffered `python -u` output, process backstop `E2E_TIMEOUT`
  (default 900s).

## [v0.1.0] - 2026-09-04

### Added

- **Lab5.QMS customization package:** DACs, graphs, and `QM*` screens for
  inspection plans, dock-receipt QC Hold, CoA result ingestion, lot
  disposition, and non-conformance reports. Namespace `Lab5.QMS`; zip
  `Lab5_QMS_Customization.zip`.
- **REST endpoint `QMS/22.200.001`:** InspectionPlan GET (`$expand=Tests`),
  InspectionOrder GET/PUT, NonConformance GET/POST for the companion
  ingestion engine.
- **Lot gate:** `UsrQMSInspectionRequired` on PO Receipt release puts the
  lot in `QC Hold` and inserts a draft InspectionOrder. Pass → Released;
  fail → Quarantine + NCR. QC Hold → Released requires `Quality Manager`
  or the ingestion service account.
- **Pack + live e2e:** `gmake pack` builds the CustomizationApi zip;
  `gmake check` publishes it and proves schema + pass/fail paths on the
  `.env` tenant.
- **GitHub release path:** `gmake release major|minor|patch` bumps the
  version, promotes CHANGELOG, packs the zip, tags `vX.Y.Z`, and publishes
  via `gh release create`.

