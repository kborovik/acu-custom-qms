# Changelog

## Unreleased

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

