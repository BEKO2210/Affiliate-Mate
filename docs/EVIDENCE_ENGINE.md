# Evidence Engine

Affiliate-Mate v0.2 introduces a small, deliberately strict evidence layer. Its job is not to predict success. Its job is to make changing inputs auditable and reproducible.

## Why evidence is separate from candidates

A normalized product candidate is convenient for scoring, but values such as price, commission rate, search demand, competition, and intent are observations made at a point in time. If those values are overwritten in place, the system loses the answer to three important questions:

1. Where did this value come from?
2. When was it observed?
3. Was it still valid when the decision was made?

The evidence store preserves those questions independently from the scoring model.

## Observation model

Each `EvidenceObservation` contains:

| Field | Meaning |
|---|---|
| `product_id` | Stable normalized product identifier |
| `signal` | Signal name, e.g. `monthly_searches` |
| `value` | Finite numeric observation |
| `source` | Provider or human source identifier |
| `marketplace` | Market context, e.g. `DE` |
| `observed_at` | Timezone-aware observation time |
| `confidence` | Explicit 0–1 confidence value |
| `expires_at` | Optional validity boundary |
| `unit` | Optional unit such as `EUR` |
| `metadata` | JSON-serializable source context |

Naive timestamps are rejected. Non-finite numbers are rejected. Expiry cannot be earlier than or equal to the observation time.

## SQLite schema

Schema version `1` uses two tables:

- `schema_meta` — stores the schema version
- `evidence_observations` — append-oriented observations

The observation identity is unique across:

```text
(product_id, signal, source, marketplace, observed_at)
```

A repeated insert of that identity is treated as an idempotent duplicate. A provider that wants to issue a new observation should use a new observation timestamp.

Indexes support product/signal point-in-time lookup and expiry housekeeping. File-backed databases enable SQLite WAL mode and a busy timeout.

## Point-in-time lookup

`store.latest(..., as_of=T)` selects the newest observation that:

- belongs to the requested product, signal, and marketplace
- was observed at or before `T`
- has not expired at `T`, unless `include_expired=True`

This makes historical re-evaluation possible and prevents future observations from leaking into an earlier decision.

An important consequence: if a newer observation has expired but an older observation is still valid, the older valid observation may be selected. The store does not equate "newest ever" with "valid now."

## Candidate resolution

`resolve_candidate_from_store()` currently supports these normalized signals:

- `price`
- `commission_rate`
- `monthly_searches`
- `youtube_competition`
- `buyer_intent`
- `content_gap`
- `evidence_quality`
- `estimated_ctr`
- `estimated_conversion_rate`

The resolver records both applied evidence and observations skipped by the configured minimum confidence.

Integer-valued signals must actually contain integral values. They are not silently truncated. A price observation with an explicit unit that conflicts with the candidate currency raises an error rather than performing an implicit conversion.

## Completeness and fail-closed behavior

CSV analysis records which columns were explicitly non-empty. The default decision policy requires:

```text
monthly_searches
youtube_competition
buyer_intent
content_gap
evidence_quality
```

If one is missing, `analyze` rejects the candidate. Valid evidence applied from the SQLite store counts as explicit evidence and can fill the missing field.

This is intentionally stricter than the legacy `score` command, which preserves v0.1 defaults for backward compatibility.

## Provider boundary

Two structural protocols define the acquisition boundary:

- `CandidateProvider` yields normalized candidates
- `EvidenceProvider` yields evidence observations for a candidate

Providers do not rank or reject products. Decision logic remains deterministic and testable in the core.

## Retention

Evidence history is retained by default. `delete_expired()` is explicit housekeeping rather than automatic deletion. That choice protects reproducibility: expired does not mean historically useless.

## Security boundary

The SQLite store contains research observations, not credentials. Provider secrets belong in environment variables or an external secret manager. Secret material should never be copied into observation metadata.

## Future migration strategy

`schema_meta.schema_version` is checked on initialization. A future schema change should ship as an explicit migration rather than silently modifying semantics. Unknown schema versions fail rather than being guessed.
