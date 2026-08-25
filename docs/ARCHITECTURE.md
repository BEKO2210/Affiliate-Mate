# Architecture

Affiliate-Mate separates **catalog acquisition**, **market evidence**, **opportunity decisions**, **editorial research**, **approval**, and **production planning** so no marketplace, data vendor, LLM, renderer, or publisher adapter becomes the system or the authority.

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
                HUMAN APPROVAL
                        |
          approval-bound research snapshot
                    SHA-256
                        |
                Approval Guard
                        |
             ProductionAuthorization
         approval event + research digest
                        |
              Grounded ScriptRequest
        approved claims + source locators
                        |
                ScriptGenerator
                        |
              Structured ScriptDocument
                FACT -> claim IDs
                        |
          +-------------+-------------+
          |             |             |
         TTS         thumbnail      metadata
          |             |             |
          +-------------+-------------+
                        |
                render adapter plan
                        |
              ProductionPackage
          lineage + plans + artifacts
                    SHA-256
                        |
             HUMAN PRODUCTION SIGNOFF
                        |
                publish dry-run
                        |
               future live publisher
```

Near-duplicate product clustering sits before expensive market collection and is advisory. Review clustering sits inside editorial research and is also advisory. Neither silently merges economics, deletes records, manufactures claims, or grants production authority.

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

1. hard gates for required or weak critical conditions
2. transparent weighted scoring for eligible opportunities

A high score cannot override a failed gate. CTR and conversion assumptions are stressed through deterministic sensitivity analysis rather than presented as certainty.

The stable automation contract remains:

```text
affiliate-mate.analysis.v1
```

A shortlist means **research further**. It never means **publish**.

## 7. Research workspace

`ResearchWorkspaceStore` can coexist in the same SQLite file as the numeric Evidence Engine because it owns a separate schema namespace.

Primary records cover:

```text
research_sources
research_claims
claim_state_events
claim_evidence_links
research_notes
note_claim_links
approval_events
approval_snapshots
```

### Source records

Sources preserve product scope, kind, title, locator, publisher, retrieval time, optional publication time, optional checksum, and optional metadata.

A source record is provenance. It does not automatically prove any claim.

### Claims

Claims are immutable base records with separate append-only state history. A rejected claim must re-enter draft before it can become supported again, preserving the intervention in history.

### Claim/evidence links

Links state exactly how a source relates to a claim:

- `supports`
- `contradicts`
- `context`

Every link carries a source locator. Claim and source must belong to the same product. Contradictions are first-class data rather than inconvenient records to discard.

### Notes

Research notes are product-scoped and explicitly linked to claims. They form the editorial bridge between raw evidence and later production.

## 8. Research completeness policy

`evaluate_research_completeness()` is a second fail-closed gate layer, independent of the commercial opportunity score.

Defaults require source diversity, active supported claims, notes covering active claims, explicit support links, stronger independent evidence for high-risk claims, and no unresolved contradictory links on supported claims.

Rejected claims remain in history but do not count as active claims. Thresholds are explicit policy, not hidden model behavior.

## 9. Approval integrity

A raw approval state is not a sufficient production capability.

When a guarded transition enters `APPROVED`, Affiliate-Mate records a deterministic SHA-256 of the editorial research revision. The snapshot includes sources, claims, complete claim-state history, evidence links, notes, and note/claim relationships. Approval events themselves are excluded from the digest so recording approval does not mutate the package being approved.

`evaluate_approval_guard()` passes only when:

```text
raw state == APPROVED
AND research completeness == PASS
AND approval snapshot exists
AND approved research digest == current research digest
```

Any later research mutation makes the old approval stale automatically.

The research brief exposes this effective readiness rather than treating a historical `APPROVED` row as permanent permission.

## 10. User-supplied review analysis

Review analysis operates only on user-supplied or properly licensed input. It does not scrape review websites.

The deterministic baseline performs product/marketplace filtering, normalized-text SHA-256 duplicate detection, de-duplication before clustering, explainable token-overlap clustering, common-term labeling, and coarse orientation from supplied ratings.

This is editorial triage, not semantic ground truth and not product evidence by itself.

## 11. Research brief boundary

`build_research_brief()` combines the current opportunity analysis with audited research records. It renders recorded claims; it does not generate new claim text.

Outputs include Markdown and the versioned JSON contract:

```text
affiliate-mate.research-brief.v1
```

The brief exposes opportunity decision, sensitivity, evidence resolution, source provenance, claim state/evidence links, notes, optional review themes, completeness, approval state, and approval freshness.

## 12. Production authorization boundary

v0.6 does not hand production code a generic boolean. `require_production_authorization()` derives a scoped capability from the effective approval guard:

```text
ProductionAuthorization {
    product_id
    approval_event_id
    research_digest
    created_at
}
```

This object is revision-specific, not permanent. `assert_authorization_current()` re-runs the research approval guard and compares both approval event and research digest at the point of use.

That closes the basic time-of-check/time-of-use failure mode where research is approved, mutated, and then rendered under the stale earlier decision.

## 13. Grounded script boundary

`ScriptGenerator` is provider-neutral. Generation receives `ScriptRequest`, not unrestricted authority over the research database.

A request contains:

- product + approved research digest
- language + working title
- supported claims
- source IDs and precise source locators
- spoken + description disclosures
- explicit generation constraints

`ScriptDocument` is structured. A `FACT` segment must contain claim IDs. `validate_script_grounding()` rejects claims that are unknown, cross-product, no longer supported, or tied to stale research authorization.

This guarantees structural lineage. It does **not** prove that arbitrary generated prose is semantically equivalent to a referenced claim. That residual risk is one reason the production package has a separate human signoff.

The built-in `StrictTemplateScriptGenerator` is deliberately conservative: it reuses approved claim text and exists as a deterministic safe baseline.

## 14. Production adapter contracts

External production systems are interfaces:

```text
ScriptGenerator
TTSAdapter
VideoRenderAdapter
ThumbnailAdapter
PublisherAdapter
```

v0.6 ships planning-only implementations:

```text
strict-template-v1
dry-run-tts-v1
dry-run-video-v1
dry-run-thumbnail-v1
dry-run-youtube-v1
```

The dry-run adapters compute deterministic input digests and expose intended parameters without contacting external services.

A future live adapter should separate `plan` from `execute`. `execute` must re-check current authorization immediately before its external side effect.

## 15. Metadata, disclosure, and thumbnail boundaries

Affiliate metadata requires an absolute HTTP(S) URL and an explicit description disclosure. German and English disclosure strings are convenience templates, not a legal-compliance oracle.

Thumbnail planning is intentionally constrained: the default brief tells renderers not to add ratings, awards, prices, performance claims, or comparison badges unless they are explicitly approved claims.

Neither metadata nor thumbnail generation can grant publishing authority.

## 16. Content-addressed artifact manifest

`ArtifactRecord` captures:

```text
logical_name
kind
safe relative path
media type
SHA-256
byte length
```

Absolute paths, parent traversal, and backslash ambiguity are rejected. A strict publish dry-run can reopen every artifact under an explicit root and verify byte count + SHA-256.

This detects a local file being replaced after the production package was assembled.

Required live-publish artifact kinds currently are script, narration, video, thumbnail, and metadata. Captions are supported as an artifact kind but are not a hard requirement yet.

## 17. Production package and second human checkpoint

Research approval authorizes one research revision. It does not automatically approve generated copy or rendered media.

`ProductionPackage` binds:

- product ID
- approval event ID
- approved research digest
- structured script
- metadata + disclosure
- thumbnail brief
- adapter plans
- artifact records
- package creation time

The canonical package has its own SHA-256 digest.

`ProductionSignoff` is a second human checkpoint bound to that exact package digest. Any mutation to the package invalidates the old signoff.

This signoff is an integrity/audit binding, not an asymmetric cryptographic identity signature. Stronger signatures can be layered later without changing the package digest model.

## 18. Publish dry-run boundary

`build_publish_dry_run()` is intentionally non-side-effecting. It checks:

1. research authorization is still current
2. package approval/research lineage matches authorization
3. factual script claim lineage is still valid
4. human production signoff matches the exact package digest
5. affiliate disclosure remains in metadata
6. required artifact records are present
7. artifact bytes match the content-addressed manifest
8. the selected publisher plan itself is non-side-effecting

The result is versioned as:

```text
affiliate-mate.publish-plan.v1
```

`ready_for_live_adapter=true` is not a publish. It says local preconditions passed for a later, separately implemented live adapter.

## 19. Versioned production contracts

v0.6 exposes:

```text
affiliate-mate.production-authorization.v1
affiliate-mate.script.v1
affiliate-mate.production-package.v1
affiliate-mate.production-signoff.v1
affiliate-mate.publish-plan.v1
```

Deserializers fail on unknown schema versions instead of silently guessing compatibility.

## 20. Future learning boundary

v0.7 may ingest realized traffic and affiliate outcomes, but future observations must never alter what an earlier decision supposedly knew.

Learning therefore needs separate event time and ingestion time, scoring-policy versioning, explicit train/evaluation splits, walk-forward evaluation, and target-leakage guards. Policy changes should be backtested before they can affect candidate ranking.

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
    |
ApprovalGuard failure
    |
ProductionAuthorizationError
    |
ScriptGroundingError
    |
ProductionPackage / artifact invariant failure
    |
ProductionSignoff mismatch
    |
Publish dry-run failure
```

Failures remain explicit rather than being flattened into fake data or permissive defaults.

## Security and correctness constraints

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
- research approval cannot bypass completeness gates
- stale research approval cannot authorize production
- production authorization is re-checked at point of use
- factual script segments require supported claim lineage
- an LLM reference to a claim ID is not treated as proof of semantic correctness
- production package mutation invalidates human package signoff
- artifact replacement is detectable through content hashes
- metadata must carry the configured disclosure
- the v0.6 publisher is planning-only
- generation adapters do not implicitly receive publishing authority
- any future live publisher must re-check authorization + package signoff immediately before side effects
