# Acumatica QMS Customization (`acu-custom-qms`)

Acumatica Cloud xRP customization package **`CanNordic.QMS`**: inspection plans,
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
CanNordic_QMS_Customization.zip
```

## Family

| Repo | Layer |
| --- | --- |
| `acu-google-qms` | GCP ingestion |
| `acu-gitops-qms` | tenant GitOps seed |
| `acu-custom-qms` | Acumatica customization project |
