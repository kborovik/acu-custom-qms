# Acumatica QMS Customization (`acu-custom-qms`)

Acumatica Cloud xRP customization package **`Lab5.QMS`**: inspection plans,
dock-receipt quarantine, CoA result ingestion, lot disposition, and
non-conformance reports.

This is the ERP-side companion to:

- [`acu-google-qms`](https://github.com/kborovik/acu-google-qms) — GCP CoA ingestion / reasoning engine
- [`acu-gitops-qms`](https://github.com/kborovik/acu-gitops-qms) — CanNordic tenant seed

## Specification

Minimum technical spec: [`domain/ACUMATICA_QMS_EXTENSION_SPEC.md`](domain/ACUMATICA_QMS_EXTENSION_SPEC.md).

The package delivers DACs, graphs, screens (`QM*`), and the `QMS/22.200.001`
REST endpoint used by the ingestion engine. Shipped artifact:

```
Lab5_QMS_Customization.zip
```

Installable Click CLI (`uv run lab5-qms`): pack that zip, publish via
CustomizationApi, and seed post-publish Role `Quality Manager` plus
`RolesInGraph` Delete on the QM screens.

```sh
uv run lab5-qms pack      # write Lab5_QMS_Customization.zip
uv run lab5-qms           # pack + publish + seed
```

## Family

| Repo | Layer |
| --- | --- |
| `acu-google-qms` | GCP ingestion |
| `acu-gitops-qms` | tenant GitOps seed |
| `acu-custom-qms` | Acumatica customization project |

## Release

Notes live in [`CHANGELOG.md`](CHANGELOG.md). Append user-facing work under
`## Unreleased` (`### Added` / `### Changed` / `### Fixed`). Empty Unreleased
hard-fails — nothing to ship.

```sh
gmake release patch   # or minor | major
```

`gmake release` is the sole path: local tests, bump `pyproject.toml`, promote
CHANGELOG, tag `vX.Y.Z`, pack `Lab5_QMS_Customization.zip`, push, then
`gh release create` with the zip attached. There is no CI publisher — `gh`
runs locally. Requires a clean tree, `gh` authenticated, and bullets under
`## Unreleased`.

## License

This project is licensed under the PolyForm Noncommercial License 1.0.0.
Noncommercial use is free under that license.

Commercial use requires a separate license — contact [lab5.ca](https://lab5.ca).

See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Copyright 2026 Konstantin Borovik.
