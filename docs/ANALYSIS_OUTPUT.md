# Analysis JSON contract

The v0.2 automation contract is identified by:

```json
{"schema_version": "affiliate-mate.analysis.v1"}
```

Consumers should branch on `schema_version` instead of assuming an unversioned shape.

## Top-level shape

```text
schema_version
policy
summary
results[]
```

`policy` contains every threshold used for the run. `summary` contains `total`, `shortlisted`, and `rejected`. Each result contains the normalized product, input completeness, decision report, sensitivity report, and optional evidence-resolution audit trail.

## Decision report

Every hard gate contains:

```text
code
passed
actual
operator
threshold
message
```

Rejected products also expose `rejection_reasons`. Consumers should prefer the stable `code` and `passed` fields for logic; `message` is intended for humans and may improve over time.

## Score report

The score payload contains the complete 0–100 component breakdown, commission per sale, and base estimated value per 1,000 views. `explanations` are deterministic human-readable summaries of the strongest contribution, weakest contribution, and economics assumption.

## Sensitivity report

The default sensitivity report evaluates a 3x3 grid of CTR and conversion multipliers:

```text
0.6x, 1.0x, 1.4x
```

The payload includes all points plus floor, base, ceiling, downside percentage, and upside percentage. This is not a probability distribution; it is a deterministic assumption stress test.

## Evidence resolution

When `--evidence-db` is not used, `evidence_resolution` is `null`.

When it is used, the object contains:

- `applied` — persisted observations that replaced candidate values
- `skipped_low_confidence` — latest valid observations ignored by the configured confidence floor

Each observation retains source, time, expiry, confidence, unit, and metadata.

## Compatibility policy

Within `affiliate-mate.analysis.v1`, new optional fields may be added, but existing field meaning should not change. A breaking semantic or structural change requires a new schema version.
