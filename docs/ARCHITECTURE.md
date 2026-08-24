# Architecture

Affiliate-Mate separates **catalog acquisition**, **market evidence**, **resolution**, **decision logic**, and **content production** so that no single marketplace, data vendor, or LLM becomes the system.

```text
external catalogs             independent market sources
       |                               |
       v                               v
   CatalogItem                    observations
       |                               |
commission schedule                 SQLite
       |                               |
research signals <--------------------+
       |
       v
 ProductCandidate
       |
 evidence resolution
       |
 required gates
       |
 transparent score
 + sensitivity
       |
   shortlist
       |
 human research / approval
       |
 future production adapters
```

## 1. Catalog acquisition

Catalog adapters discover products and normalize provider-specific payloads into `CatalogItem` records. A catalog adapter may expose facts such as:

- provider product ID
- title
- marketplace
- current catalog price and currency
- product detail URL
- brand
- provider/category label

It must **not** decide whether a product is commercially attractive or invent missing market evidence.

v0.3 introduces `CatalogSearchProvider` plus two implementations:

- `MockCatalogProvider` — deterministic, credential-free contributor fixture
- `AmazonCatalogProvider` — backed by Amazon Creators API

The existing v0.2 `CandidateProvider` and `EvidenceProvider` contracts remain valid for normalized candidate/evidence sources.

## 2. Catalog economics boundary

Affiliate commission rates are not treated as permanent catalog facts. `CommissionSchedule` is explicit user-supplied configuration/evidence with normalized marketplace/category keys and deterministic wildcard precedence.

`candidate_from_catalog()` only promotes a `CatalogItem` to `ProductCandidate` after the caller supplies:

- price
- currency
- commission category
- matching commission rule
- independent `ResearchSignals`

This prevents a catalog API from silently injecting guessed demand, competition, buyer intent, or economics into scoring.

## 3. Provider transport boundary

Live APIs use `JsonHttpClient`, which isolates network mechanics from provider parsing.

Transport behavior is injectable so tests can deterministically exercise:

- successful responses
- transient HTTP failures
- rate-limit responses
- `Retry-After`
- exponential backoff
- malformed JSON
- non-retryable failures

Retries are bounded. Provider outages cannot become infinite request loops.

Amazon-specific OAuth/token caching and response semantics remain in `amazon_creators.py`; generic HTTP behavior remains in `http_client.py`.

## 4. Normalized candidate

`ProductCandidate` is the stable scoring shape. It contains current working values without vendor-specific response objects.

The legacy `score` path can operate directly on this model. The stricter `analyze` path additionally preserves input completeness through `CandidateInput`.

## 5. Evidence store

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

## 6. Evidence resolution

`resolve_candidate_from_store()` overlays the latest valid persisted observation for each supported candidate signal. The resolution result keeps an audit trail of what was applied and what was skipped for low confidence.

Resolution is strict where silent coercion would be dangerous. Integer signals cannot contain fractions, and explicitly unit-tagged price evidence cannot cross currencies implicitly.

Catalog parsing follows the same philosophy: an Amazon price whose currency conflicts with the configured marketplace is rejected rather than silently converted.

## 7. Decision engine

The decision engine has two layers:

1. **hard gates** — reject missing/weak critical conditions
2. **transparent weighted score** — rank eligible opportunities

All thresholds and component weights are inspectable. Rejected candidates retain their score for diagnosis, but a high score cannot override a failed hard gate.

## 8. Sensitivity analysis

Base CTR and conversion assumptions are stressed over a deterministic grid. This exposes how fragile the EV/1K estimate is instead of treating a single point estimate as certainty.

## 9. Automation boundary

The versioned `affiliate-mate.analysis.v1` JSON contract serializes policy, gates, score, sensitivity, and evidence resolution. This is the intended integration boundary for future agents and workflows.

Catalog discovery has its own JSON output and remains upstream. This keeps provider acquisition independent from the stable decision-report contract.

## 10. Human approval checkpoint

A shortlist is permission to research further, not permission to publish. Future production adapters must preserve an explicit approval boundary for product claims, rights, disclosures, and editorial quality.

## 11. Production adapters

Script, voice, video, thumbnail, and publishing tools belong at the edge of the system. The core remains useful when none are configured.

## Error boundaries

Failure classes remain explicit rather than being flattened into `None` or fake data:

```text
TransportError
    |
HttpRequestError
    |
provider-specific API error
    |
provider protocol/semantic error
    |
local validation error
```

Callers can therefore distinguish a temporary network problem from expired credentials, an API rejection, malformed provider data, or invalid local configuration.

## Design constraints

- no dependency on brittle storefront HTML scraping
- no secret keys committed to the repository
- no provider credential in exception messages
- no hard-coded affiliate commission rates presented as permanent truth
- no revenue claim without visible assumptions
- deterministic ranking, gate, resolution, sensitivity, transport, and provider-contract tests
- retries are bounded and non-retryable errors fail immediately
- adapters fail closed on invalid critical data
- timestamps and provenance survive normalization
- point-in-time analysis must not read future observations
- evidence cannot silently cross marketplace/currency boundaries
- catalog discovery cannot bypass required research evidence
- no automatic publish path may bypass future approval state
