# Architecture

Affiliate-Mate separates **acquisition**, **evidence**, **resolution**, **decision logic**, and **content production** so that no single marketplace, data vendor, or LLM becomes the system.

## 1. Sources

Source adapters acquire candidates or observations. They normalize provider-specific payloads but do not decide whether a product is a good opportunity.

Two structural contracts exist in v0.2:

- `CandidateProvider`
- `EvidenceProvider`

Planned source types include supported affiliate catalog APIs, keyword/trend sources, video-search competition sources, manual/CSV inputs, and user-owned exports.

## 2. Normalized candidate

`ProductCandidate` is the stable scoring shape. It contains current working values without vendor-specific fields.

The legacy `score` path can operate directly on this model. The stricter `analyze` path additionally preserves input completeness through `CandidateInput`.

## 3. Evidence store

`SQLiteEvidenceStore` persists numeric observations with:

- product and signal
- source
- marketplace
- observed timestamp
- confidence
- optional expiry
- optional unit
- JSON metadata

The store is append-oriented and point-in-time queryable. History and current validity are separate concepts.

## 4. Evidence resolution

`resolve_candidate_from_store()` overlays the latest valid persisted observation for each supported candidate signal. The resolution result keeps an audit trail of what was applied and what was skipped for low confidence.

Resolution is strict where silent coercion would be dangerous. Integer signals cannot contain fractions, and explicitly unit-tagged price evidence cannot cross currencies implicitly.

## 5. Decision engine

The decision engine has two layers:

1. **hard gates** — reject missing/weak critical conditions
2. **transparent weighted score** — rank eligible opportunities

All thresholds and component weights are inspectable. Rejected candidates retain their score for diagnosis, but a high score cannot override a failed hard gate.

## 6. Sensitivity analysis

Base CTR and conversion assumptions are stressed over a deterministic grid. This exposes how fragile the EV/1K estimate is instead of treating a single point estimate as certainty.

## 7. Automation boundary

The versioned `affiliate-mate.analysis.v1` JSON contract serializes policy, gates, score, sensitivity, and evidence resolution. This is the intended integration boundary for future agents and workflows.

## 8. Human approval checkpoint

A shortlist is permission to research further, not permission to publish. Future production adapters must preserve an explicit approval boundary for product claims, rights, disclosures, and editorial quality.

## 9. Production adapters

Script, voice, video, thumbnail, and publishing tools belong at the edge of the system. The core remains useful when none are configured.

## Design constraints

- no dependency on scraping private or brittle page markup
- no secret keys committed to the repository
- no revenue claim without visible assumptions
- deterministic ranking, gate, resolution, and sensitivity tests
- adapters fail closed on invalid critical data
- timestamps and provenance survive normalization
- point-in-time analysis must not read future observations
- persisted evidence cannot silently cross marketplace/currency boundaries
- no automatic publish path may bypass future approval state
