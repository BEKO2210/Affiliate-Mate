# Architecture

Affiliate-Mate separates **catalog acquisition**, **market evidence**, **resolution**, **decision logic**, and **content production** so that no single marketplace, data vendor, or LLM becomes the system.

```text
 external catalogs                  independent market sources
        |                         /        |         |        \
        v                    keyword    YouTube    trend    replay
    CatalogItem                    \        |         |        /
        |                           \       |         |       /
 commission schedule                 EvidenceObservation
        |                                      |
        +--------------------+-----------------+
                             v
                     SQLite evidence store
                  provenance + time + expiry
                             |
                     point-in-time resolution
                             |
                      ProductCandidate
                             |
                       required gates
                             |
                 transparent score + sensitivity
                             |
                          shortlist
                             |
                  human research / approval
                             |
                  future production adapters
```

Near-duplicate clustering sits before expensive live collection and is advisory: it groups likely variants but never merges economics or deletes candidates.

## 1. Catalog acquisition

Catalog adapters discover products and normalize provider-specific payloads into `CatalogItem` records. A catalog adapter may expose facts such as provider product ID, title, marketplace, price/currency, product detail URL, brand, and category label.

It must **not** decide whether a product is commercially attractive or invent missing market evidence.

Current implementations:

- `MockCatalogProvider` — deterministic, credential-free contributor fixture
- `AmazonCatalogProvider` — backed by Amazon Creators API

The existing `CandidateProvider` and `EvidenceProvider` protocols remain the provider-neutral boundaries for normalized candidates and observations.

## 2. Catalog economics boundary

Affiliate commission rates are not treated as permanent catalog facts. `CommissionSchedule` is explicit user-supplied configuration/evidence with normalized marketplace/category keys and deterministic wildcard precedence.

`candidate_from_catalog()` only promotes a `CatalogItem` after the caller supplies a valid price/currency, commission category, matching commission rule, and independent research signals.

## 3. Market intelligence acquisition

v0.4 adds explicit evidence producers instead of filling research fields with defaults:

- `CSVKeywordEvidenceProvider` → `monthly_searches`, `buyer_intent`
- `YouTubeCompetitionProvider` → `youtube_competition`, `content_gap`
- `CSVTrendEvidenceProvider` → auxiliary `trend_strength`, `seasonality`
- `ReplayEvidenceProvider` → deterministic captured numeric observations

The trend signals are intentionally auxiliary in v0.4. They are preserved and auditable but do not silently alter the existing score. Any future scoring change must be explicit and backtestable.

## 4. Source budgets and transport

Live HTTP APIs use `JsonHttpClient`, which isolates retries and transport failures from provider semantics. Retries are bounded and transient failures can honor `Retry-After`.

`SourceCallBudget` adds a second safety boundary: an in-process workflow can reserve named API operations against explicit limits. Multi-operation reservations are atomic, so a failed reservation does not partially consume another operation's allowance.

The YouTube client reserves one `youtube.search.list` and one `youtube.videos.list` operation before collecting a landscape. The CLI exposes a maximum number of YouTube product collections per process.

These call budgets are safety rails, not replacements for provider-side quota enforcement.

## 5. Signal freshness

`SignalFreshnessPolicy` attaches default expiries to time-sensitive observations:

- price: 1 day
- commission rate: 7 days
- YouTube competition/content gap: 7 days
- buyer intent: 14 days
- trend strength: 14 days
- monthly search demand: 30 days
- seasonality/evidence quality: 30 days

An explicit provider expiry always wins. Generic policy never extends a producer-supplied validity window.

## 6. Collection orchestration

`collect_evidence()` executes independent evidence providers for one candidate and validates every returned observation before storage.

Provider run states are:

- `success`
- `empty`
- `failed`

A provider is marked failed when it raises or returns evidence for another product or marketplace. In normal mode, valid observations from unrelated providers can still be persisted. `fail_fast` is available for stricter workflows.

This prevents a broken adapter from contaminating another candidate's evidence history while still making partial collection observable.

## 7. Normalized candidate

`ProductCandidate` remains the stable scoring shape. It contains working values rather than vendor-specific response objects. The stricter analysis path additionally preserves input completeness through `CandidateInput`.

## 8. Evidence store

`SQLiteEvidenceStore` persists numeric observations with product, signal, source, marketplace, observed timestamp, confidence, expiry, unit, and strict JSON metadata.

The store is append-oriented and point-in-time queryable. History and current validity are separate concepts.

## 9. Evidence resolution

`resolve_candidate_from_store()` overlays the latest valid persisted observation for each supported decision signal and retains an audit trail of applied or skipped evidence.

Resolution fails closed where coercion would be dangerous: integer signals cannot contain fractions and explicitly unit-tagged price evidence cannot cross currencies implicitly.

## 10. Decision engine

The decision engine has two layers:

1. **hard gates** — reject missing or weak critical conditions
2. **transparent weighted score** — rank only eligible opportunities

A high weighted score cannot override a failed hard gate.

## 11. Sensitivity analysis

Base CTR and conversion assumptions are stressed over a deterministic grid. This exposes how fragile EV/1K is instead of presenting a single point estimate as certainty.

## 12. Automation boundaries

The versioned `affiliate-mate.analysis.v1` contract remains the stable decision-report boundary.

Catalog discovery and market-intelligence collection have separate outputs. This is deliberate: acquisition contracts may evolve without silently changing the decision-report schema.

## 13. Human approval checkpoint

A shortlist is permission to research further, not permission to publish. Future research and production adapters must preserve explicit approval for product claims, rights, disclosures, and editorial quality.

## 14. Production adapters

Script, voice, video, thumbnail, and publishing tools belong at the edge of the system. The analysis core remains useful when none are configured.

## Error boundaries

```text
TransportError
    |
HttpRequestError
    |
provider-specific API error
    |
provider protocol/semantic error
    |
collection validation failure
    |
local decision gates
```

Call-budget exhaustion is explicit (`BudgetExceededError`) rather than being disguised as missing evidence.

## Design constraints

- no dependency on brittle storefront or YouTube HTML scraping
- no secret keys committed to the repository
- no provider credential in normal exception messages
- no hard-coded affiliate commission rates presented as permanent truth
- no keyword-demand fabrication
- no descriptive trend metric presented as a forecast
- no revenue claim without visible assumptions
- retries and live-source call budgets are bounded
- adapters fail closed on invalid critical data
- timestamps and provenance survive normalization
- point-in-time analysis must not read future observations
- evidence cannot silently cross product, marketplace, or currency boundaries
- catalog discovery cannot bypass required research evidence
- auxiliary market signals cannot silently change the score
- no automatic publish path may bypass future approval state
