# Architecture

Affiliate-Mate separates **catalog acquisition**, **market evidence**, **opportunity decisions**, **editorial research**, and future **content production** so that no marketplace, data vendor, LLM, or publisher adapter becomes the system.

```text
 external catalogs                 independent market sources
        |                        /       |        |       \
        v                   keyword   YouTube   trend   replay
    CatalogItem                   \       |        |       /
        |                          EvidenceObservation
 commission schedule                       |
        |                           SQLite evidence history
        +---------------+------------------+
                        v
                ProductCandidate
                        |
               point-in-time resolution
                        |
                hard opportunity gates
                        |
             transparent score + sensitivity
                        |
                     shortlist
                        |
                Research Workspace
              /          |          \
          sources      claims       notes
                        |
                evidence links
          supports / contradicts / context
                        |
               claim state audit
                        |
              completeness gates
                        |
                human approval
                        |
               approved research brief
                        |
              future production adapters
```

Near-duplicate product clustering sits before expensive collection and is advisory. Review clustering sits inside editorial research and is also advisory. Neither silently merges economics, deletes records, or manufactures claims.

## 1. Catalog acquisition

Catalog adapters normalize provider-specific product payloads into `CatalogItem`. They may expose provider product ID, title, marketplace, current price/currency, product URL, brand, and category.

They must not decide commercial attractiveness or invent demand, buyer intent, competition, or commission economics.

Current implementations:

- `MockCatalogProvider` — deterministic and credential-free
- `AmazonCatalogProvider` — Amazon Creators API

Commission schedules remain explicit user-supplied data rather than permanent hard-coded marketplace truth.

## 2. Market intelligence acquisition

Explicit evidence producers fill market-research signals:

- `CSVKeywordEvidenceProvider` → `monthly_searches`, `buyer_intent`
- `YouTubeCompetitionProvider` → `youtube_competition`, `content_gap`
- `CSVTrendEvidenceProvider` → auxiliary `trend_strength`, `seasonality`
- `ReplayEvidenceProvider` → deterministic captured numeric observations

Providers acquire observations. They do not decide whether a product passes.

## 3. Transport, quotas, and freshness

Live APIs use `JsonHttpClient` with bounded retry behavior. `SourceCallBudget` makes process-local collection limits explicit and atomic.

`SignalFreshnessPolicy` attaches signal-specific TTLs. Producer-supplied expiry always wins; generic policy never extends it.

Market evidence is therefore treated as time-dependent data, not permanent truth.

## 4. Evidence store

`SQLiteEvidenceStore` persists numeric observations with:

- product and marketplace
- signal/value/unit
- source provenance
- observed timestamp
- confidence
- optional expiry
- strict JSON metadata

The store is append-oriented and point-in-time queryable. Historical evaluation excludes future observations.

## 5. Evidence resolution

`resolve_candidate_from_store()` overlays the latest valid persisted observations onto a normalized candidate and retains an audit trail of applied and skipped evidence.

Resolution fails closed when coercion would be dangerous. Examples include fractional integer signals and cross-currency price evidence.

## 6. Opportunity decision boundary

The opportunity engine has two layers:

1. hard gates for required/weak critical conditions
2. transparent weighted scoring for eligible opportunities

A high score cannot override a failed gate. CTR and conversion assumptions are stressed through deterministic sensitivity analysis rather than presented as certainty.

The stable automation contract remains:

```text
affiliate-mate.analysis.v1
```

A shortlist means **research further**. It never means **publish**.

## 7. Research workspace

v0.5 adds `ResearchWorkspaceStore`, which can coexist in the same SQLite file as the numeric Evidence Engine because it owns a separate schema namespace (`research_schema_meta`).

Primary tables:

```text
research_sources
research_claims
claim_state_events
claim_evidence_links
research_notes
note_claim_links
approval_events
```

### Source records

Sources preserve product scope, kind, title, locator, publisher, retrieval time, optional publication time, optional checksum, and optional metadata.

A source record is provenance. It does not automatically prove any claim.

### Claims

Claims are immutable base records with separate append-only state history:

```text
DRAFT -> SUPPORTED
   |       |
   |       +----> DISPUTED
   |                 |
   +----> REJECTED <-+
             |
             +----> DRAFT
```

A rejected claim cannot jump directly to supported. It must re-enter draft, leaving a visible audit history.

### Claim/evidence links

Links state exactly how a source relates to a claim:

- `supports`
- `contradicts`
- `context`

Every link carries a source locator (page, section, timestamp, record identifier, etc.). Claim and source must belong to the same product.

Contradiction is first-class data. It is not silently discarded to make a product look better.

### Notes

Research notes are product-scoped and explicitly linked to claims. Notes are the editorial bridge between raw evidence and a later script package.

## 8. Research completeness policy

`evaluate_research_completeness()` is a second fail-closed gate layer, independent of the commercial opportunity score.

Defaults require:

- at least two research sources
- at least two distinct publishers
- at least one active claim
- at least one research note
- every active claim explicitly in `supported` state
- every active claim represented in a note
- ordinary claims supported by at least one source
- high-risk claims supported by at least two sources
- high-risk claims supported by at least two distinct publishers
- no contradictory links on supported claims

Rejected claims remain in history but do not count as active claims.

These thresholds are policy, not hidden model behavior.

## 9. Human approval state machine

Product approval is append-only:

```text
DRAFT -> IN_REVIEW -> APPROVED
          |   ^           |
          |   |           |
          v   |           v
       REJECTED          IN_REVIEW
          |
          +-----> DRAFT
```

Approval transitions support an `expected_state` parameter. If another reviewer changed the state first, the write fails with a conflict rather than overwriting the newer decision.

`APPROVED` is special: completeness is evaluated immediately before the event is appended. Failed completeness means **no approval event is written**.

An approved package can be reopened when new evidence appears.

## 10. User-supplied review analysis

Review analysis operates only on user-supplied or properly licensed input. It does not scrape review websites.

The deterministic baseline:

1. strict product + marketplace filtering
2. normalized-text SHA-256 fingerprints
3. exact duplicate counting
4. duplicate removal before clustering
5. explainable token-overlap similarity
6. transitive union-find theme grouping
7. common-term labels
8. coarse orientation from supplied numeric ratings

This is editorial triage, not semantic ground truth and not product evidence by itself.

## 11. Research brief boundary

`build_research_brief()` combines the current opportunity analysis with audited research records. It renders recorded claims; it does not generate new claim text.

Outputs:

- Markdown with deterministic `S1`, `S2`, ... source references
- versioned JSON:

```text
affiliate-mate.research-brief.v1
```

The brief includes opportunity decision, sensitivity, optional persisted evidence resolution, research completeness, source provenance, claim states, evidence links, notes, optional review themes, and product approval state.

## 12. Future production boundary

v0.6 script/TTS/render/thumbnail/metadata adapters belong downstream of the approved research package.

The intended invariant is stronger than "human in the loop":

> **A production adapter must not accept an unapproved research package, and a live publishing adapter must not bypass that approval state.**

Production should consume structured claim IDs/source references so unsupported claims cannot silently appear during generation.

## Error boundaries

```text
TransportError
    |
HttpRequestError / provider API error
    |
provider protocol/semantic error
    |
collection validation failure
    |
opportunity hard gates
    |
research source/claim invariant failure
    |
ResearchConflictError / invalid state transition
    |
ResearchApprovalBlocked
```

Failures remain explicit rather than being flattened into fake data or permissive defaults.

## Design constraints

- no dependency on brittle storefront or YouTube HTML scraping
- no secret keys committed to the repository
- no provider credential in normal exception messages
- no hard-coded affiliate commission rates presented as permanent truth
- no keyword-demand fabrication
- no descriptive trend metric presented as a forecast
- no revenue estimate without visible assumptions
- retries and external-call budgets are bounded
- timestamps and provenance survive normalization
- historical analysis cannot read future evidence
- evidence cannot silently cross product, marketplace, or currency boundaries
- a source cannot silently become a supported claim
- contradictory evidence cannot silently disappear
- rejected claims remain auditable
- high-risk claims require stronger independent evidence
- product approval cannot bypass completeness gates
- future production cannot bypass explicit approval
