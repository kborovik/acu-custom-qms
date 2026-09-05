# Changelog

## Unreleased

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

