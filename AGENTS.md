# AGENTS.md

This repository is the Acumatica Cloud xRP customization package `Lab5.QMS`.
It holds DACs, graphs, `QM*` screens, and the `QMS/22.200.001` REST endpoint.
Spec: [`README.md`](README.md).
Control: [`SPEC.md`](SPEC.md).

Related work lives in sibling repos.
File defects and changes there, not here:

- GCP CoA ingestion and reasoning engine:
  [`kborovik/acu-google-qms`](https://github.com/kborovik/acu-google-qms)
- CanNordic tenant GitOps seed (`acu` YAML):
  [`kborovik/acu-gitops-qms`](https://github.com/kborovik/acu-gitops-qms)
- `acu` CLI:
  [`kborovik/acumatica-cli`](https://github.com/kborovik/acumatica-cli)

This repo has no `config/` seed.
Do not `acu apply` / `diff` / `run` from here.
Never print `.env` secrets.

## Live e2e (`acu` + `.env`)

Recipes (never `acu check` — destructive tenant rebuild):

| Recipe | What it does |
| --- | --- |
| `gmake check` | `ruff format --check`, `ruff check`, unit tests (no tenant) |
| `gmake build` | compile `Lab5.QMS.dll` if `QMS/Lab5.QMS` C# changed; write zip |
| `gmake deploy` | build zip + CustomizationApi publish + Role / `RolesInGraph` / `UsrQMSSetup` seed |
| `gmake e2e` | `gmake check` + `acu config check` + live e2e (publishes if the package digest differs) |
| `gmake release` | unit tests, compile if stale, bump, tag, pack, `gh release` (no e2e) |

`gmake deploy` is the inner loop after a C# / screen / SQL change.
`gmake e2e` is the proof.
There is no `gmake dll`.

Install released `acu` with `uv tool install acumatica-cli`.
This project does not depend on that package; do not launch acu through uv.

Repo-root `.env` (gitignored) is the live target. `acu` walks up from cwd to find it.

```
ACU_BASE_URL=http://<host>/AcumaticaERP
ACU_TENANT=<login>
ACU_USER=admin
ACU_PASSWORD=<secret>
```

`ACU_SSH` omitted becomes `Administrator@<base_url host>` (SSH boxes).
Present blank `ACU_SSH=` means hosted, no tenant CRUD.

Verified combo (sibling CLI): Acumatica **26.101.0225**, Default contract **25.200.001**.

### Preflight (read-only, always first)

```sh
acu config check   # REST login + Default/<api> listed; SSH ping if ACU_SSH set
acu config show    # resolved .env; password redacted
acu tenant list    # SSH; confirm ACU_TENANT exists
```

`ok rest` + `ok endpoints` = session is good.
Missing `matrix.yaml` is a warn here, not a fail.

**Never** `acu check` from this repo — that is a destructive cold tenant rebuild (`delete` then create then apply then run).

Python probes: `uv run python` (project env has click + httpx; ruff is a dev dependency used by `gmake check`).
REST and SSH go through PATH `acu` plus `acuqms.acu`.
System `python3` will not see the package.

### Package presence

`gmake deploy` / `uv run acuqms deploy` builds `Lab5_QMS_Customization.zip`, publishes via `/CustomizationApi` (same cookie session as `acu`; field is `projectContentBase64`, not `projectContents`), and seeds post-publish Role `Quality Manager` plus QM `RolesInGraph` and `UsrQMSSetup`.
Publish skip is a SHA-256 of **every zip member** (pages, SQL, DLL, `project.xml`); an ASPX-only change must republish.
Subcommands: `build`, `publish`, `seed`, `deploy`.
Naked `acuqms` prints Click help and exits 0 (does not deploy).
`gmake build` runs `acuqms build`.
Then prove the tenant has the package:

| Check | Expect |
| --- | --- |
| `POST /CustomizationApi/getPublished` | `Lab5.QMS` in `projects` (AcuBootstrap may also be present) |
| `GET /entity` | `QMS` / `22.200.001` listed |
| `GET /entity/QMS/22.200.001/swagger.json` | 200 |
| `GET /entity/QMS/22.200.001/InspectionPlan` | 200 (empty list OK) |
| `GET /entity/QMS/22.200.001/InspectionOrder` | 200 |
| `GET /entity/QMS/22.200.001/NonConformance` | 200 |
| SQL `INFORMATION_SCHEMA.TABLES` `UsrQMS%` (SSH `sqlcmd -S "(local)" -E -C`, db `AcumaticaDB`) | plan / plan-test / order / order-result / NCR tables |
| `InventoryItem` columns `UsrQMS%` / `UsrMinShelf%` | `UsrQMSInspectionRequired`, `UsrQMSInspectionPlanID`, `UsrMinShelfLifeDays` |
| `SiteMap` `ScreenID LIKE 'QM%'` | `QM.10.10.00` prefs, `QM.20.10.00` plans, `QM.30.10.00` orders, `QM.30.20.00` NCR |
| Bootstrap `NumberingSequence` `QORD` / `QNCR` | present |
| Bootstrap `Role` `Quality Manager` | present |

`GET /entity/QMS/22.200.001/...` returning `Endpoint [QMS/22.200.001] not found` means the zip is not published on this tenant.
Do not invent the endpoint.

Default-contract entities (`StockItem`, `PurchaseReceipt`, `LotSerialClass`) live under `/entity/Default/25.200.001/`.
Numbering, Role, Company, IN/PO prefs live under `/entity/Bootstrap/1.4.0/` — Default has no `NumberingSequence`.

### Functional paths (needs GitOps seed on the same tenant)

Dock / lot e2e needs inventory + IN/PO setup from sibling `acu-gitops-qms` applied to **this** `ACU_TENANT`.
Probe first:

- Bootstrap `Company` / `INPreferences` / `POPreferences` return rows
- Default `StockItem` `$top=1` is 200 with a record
- `PurchaseReceipt` GET does not 500 on missing Purchasing Preferences

If those miss, stop.
Seed the tenant from `acu-gitops-qms` (or switch `.env` `ACU_TENANT`); do not apply that YAML from this repo.

Then, against `QMS/22.200.001` + Default:

1. Item with `UsrQMSInspectionRequired=true` + plan id: release PO receipt; lot becomes `QC Hold` + draft `InspectionOrder` (PlanID, lot, vendor, receipt).
2. GET `InspectionPlan?$expand=Tests`, then PUT `InspectionOrder` results + lab cert fields, then attach CoA PDF + JSON via `/files` on the order `NoteID`.
3. Pass: `EvaluateResults` produces `OverallEvaluation` Pass; `ReleaseLotDecision` then sets lot `Released` and order Completed.
4. Fail: any required test Fail sets lot `Quarantine` + `NonConformance` inserted; allocation halted.
5. QC Hold becomes Released only as `Quality Manager` or the ingestion service account.

Read-only probes do not mutate.
Publish, receipt release, evaluate, and lot flips do — keep them on the `.env` tenant, never on an unnamed default tenant (CLI tenant guard).
