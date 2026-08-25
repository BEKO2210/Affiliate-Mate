# Architecture

Affiliate-Mate is a local-first, evidence-first system with explicit trust boundaries. Data acquisition, decision-making, editorial truth, production authorization, external side effects, and learning are separate capabilities.

The architectural rule is:

> **Later stages may consume earlier attestations; they may not retroactively change what those attestations meant.**

## End-to-end data flow

```text
external catalogs                independent market sources
       |                         /      |       |      \
       v                    keyword  YouTube  trend   replay
   CatalogItem                    \      |       |      /
       |                           EvidenceObservation
commission schedule                        |
       |                            SQLite evidence history
       +----------------+------------------+
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
             sources + claims + citations
                        |
               completeness gates
                        |
                 HUMAN APPROVAL
                        |
             research snapshot digest
                        |
             ProductionAuthorization
                        |
                grounded production
                        |
              production package digest
                        |
             HUMAN PRODUCTION SIGNOFF
                        |
               publish gate / future IO
                        |
                        v
                 realized outcomes
        views / clicks / orders / commission
        refunds / reversals / attribution
                        |
                        v
                   Learning Store
           forecasts + outcomes + policies
                        |
              calibration / drift
                        |
             holdout / walk-forward
                        |
               HUMAN POLICY DECISION
                        |
                        +------> future policy
```

The feedback arrow does **not** point backward into historical records. Learning can inform a future policy version; it cannot mutate a past forecast, decision, approval, or outcome event.

## 1. Catalog acquisition

Catalog adapters normalize provider-specific payloads into `CatalogItem`.

They may provide product identity, title, marketplace, price/currency, product URL, brand, and category. They cannot decide commercial attractiveness or fabricate demand, intent, competition, or commissions.

Current implementations include a deterministic mock provider and an Amazon Creators API adapter.

## 2. Market evidence

Numeric market observations enter through provider-neutral evidence producers and retain provenance, observation time, confidence, expiry, unit, and metadata.

Current sources include keyword exports, YouTube Data API competition evidence, trend exports, and deterministic replay fixtures.

External sources acquire observations. They do not decide whether a product passes.

## 3. Evidence history and point-in-time resolution

`SQLiteEvidenceStore` is append-oriented. `resolve_candidate_from_store()` selects the latest valid observation as of an explicit time.

Historical evaluation never reads an observation from the future. Expired or low-confidence evidence remains visible in history rather than being rewritten.

## 4. Opportunity decision boundary

`EvaluationPolicy` defines explicit hard gates. A candidate must pass all required gates before its transparent weighted score can produce a shortlist decision.

A high score cannot override missing required evidence or a failed critical threshold.

Sensitivity analysis exposes how affiliate value changes when CTR and conversion assumptions move.

A shortlist means **research further**, not **publish**.

## 5. Research truth boundary

`ResearchWorkspaceStore` separates source provenance from product claims.

Core records:

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

Claims have explicit support/contradiction/context links. Claim states and product approval states are append-only histories.

Research completeness fails closed when required source diversity, claim support, notes, or contradiction rules are not satisfied.

## 6. Revision-bound human approval

An `APPROVED` state alone is not production permission.

The approval service binds an approval event to a deterministic SHA-256 research snapshot. The effective production guard requires:

```text
raw approval == APPROVED
AND research completeness == PASS
AND approval snapshot exists
AND approval snapshot == current research digest
```

Any research mutation makes the prior approval stale.

## 7. Production boundary

v0.6 converts a current effective approval into `ProductionAuthorization`.

Production contracts retain:

- product identity,
- approval event,
- approved research digest,
- grounded claim IDs,
- script digest,
- metadata/disclosure,
- adapter plans,
- content-addressed artifacts,
- package digest.

Research approval and final production signoff are separate human checkpoints.

A publish dry-run refuses stale research authorization, unsupported factual script segments, stale package signoff, missing disclosure, missing required artifacts, artifact hash/size mismatch, or a side-effecting dry-run publisher.

## 8. Learning boundary

v0.7 adds a separate learning schema. It does not place realized outcomes into the evidence store because realized outcomes have different semantics from market evidence.

Primary tables:

```text
learning_policy_versions
learning_forecasts
learning_outcomes
learning_policy_decisions
```

### Forecast snapshots

A `ForecastSnapshot` freezes the state used for a real decision:

```text
product/content identity
marketplace/category/price/currency
prediction timestamp
outcome horizon
policy version + digest
analysis digest
candidate digest + candidate payload
explicit input-field availability tracking
accept/reject decision
opportunity score
predicted CTR
predicted conversion rate
predicted EV/1K
commission per sale
optional production-package lineage
```

The candidate digest is self-verifying. A policy must be registered before the forecast timestamp.

Forecast capture rejects resolved evidence whose observation time is later than the prediction time.

### Outcome events

`OutcomeEvent` uses immutable provider-neutral source identities and three distinct clocks:

```text
effective_at  when the behavior/economic event occurred
observed_at   when the upstream source exposed it
ingested_at   when Affiliate-Mate learned it
```

It also preserves source reporting window, product, marketplace, content ID, optional production package digest, and either a count or integer minor-unit money amount.

Outcome identities are idempotent but immutable. A replay with the same identity and different content is a conflict.

Batch outcome imports are atomic.

### No title matching

Outcomes join forecasts through explicit product/content/package lineage. Product names and video titles are presentation fields, not database keys.

### Late attribution

A backtest cutoff `T` can use an outcome only if:

```text
observed_at <= T
AND ingested_at <= T
```

The fact that an affiliate network later attributes a conversion to an earlier effective date does not make that conversion historically knowable.

## 9. Performance evaluation

A forecast has an explicit prediction horizon and a configurable reporting lag.

A performance report remains immature until:

```text
evaluated_at >= predicted_at + horizon + reporting_lag
```

Required outcome kinds must be explicitly present. Missing reports are not silently interpreted as zero.

Core observational metrics:

```text
CTR              = clicks / views
conversion rate  = orders / clicks
net commission   = gross - refunds - reversals
realized EV/1K   = 1000 × net commission / views
```

These are predictive-performance measurements, not causal estimands.

## 10. Calibration and drift

Calibration groups mature, complete reports by:

```text
marketplace × category × price band
```

CTR and conversion-rate reports expose Wilson 95% intervals. Minimum forecast/view/click/order thresholds prevent tiny cohorts from being represented as stable estimates.

Predicted-versus-realized relative error is classified as stable, drift, or insufficient according to explicit policy thresholds.

Mixed-currency cohorts fail instead of being aggregated without FX evidence.

## 11. Scoring-policy registry

A `ScoringPolicyVersion` is immutable and content-addressed.

A child policy may reference an existing parent and cannot predate it. Forecasts bind to the exact registered policy digest.

The registry is historical provenance. It is not an "active policy" switch.

## 12. Chronological backtesting

A candidate policy is evaluated on frozen historical candidates from a later holdout interval.

The boundary is explicit:

```text
policy created <= train_cutoff
forecast.predicted_at >= train_cutoff
forecast.predicted_at < evaluation_end
outcomes known by evaluated_at only
```

The historical baseline decision is replayed from the frozen candidate. Any stored-vs-replayed baseline mismatch blocks promotion eligibility. This detects code or policy drift that would make the comparison non-reproducible.

Promotion eligibility additionally requires minimum sample size, enough selected candidates, comparable realized currency, and no unacceptable realized-EV regression.

The backtest does not promote anything.

## 13. Walk-forward evaluation

A single split can be lucky.

`walk_forward_backtest()` evaluates multiple chronological folds. Each fold uses an independently versioned candidate policy, and fold evaluation windows may not move backward or overlap.

A walk-forward report is eligible only when every constituent fold satisfies its gates.

## 14. Human policy decision

Policy evaluation and policy activation are intentionally separate.

`learning_policy_decisions` records an append-only human approve/reject event tied to an evaluation digest. It does not mutate a hidden active-policy pointer.

A later operational configuration layer may choose which policy is active, but it must preserve this audit distinction.

## 15. Error boundaries

Failures remain typed/explicit rather than being flattened into plausible-looking data:

```text
transport/provider errors
        ↓
evidence validation
        ↓
opportunity gates
        ↓
research invariant / conflict
        ↓
research approval guard
        ↓
production authorization / grounding
        ↓
artifact/signoff/publish gate
        ↓
learning import conflict
        ↓
forecast time-integrity guard
        ↓
report maturity/completeness
        ↓
backtest / walk-forward promotion gates
```

## 16. Design constraints

- supported APIs or user-owned/licensed exports over brittle scraping
- provider credentials never become policy authority
- no hard-coded permanent commission truth
- evidence, claims, approvals, forecasts, and outcomes retain provenance
- historical analysis cannot read future evidence or late-ingested outcomes
- money accounting uses integer minor units
- mixed currencies are never silently aggregated
- model output is not evidence
- research approval is revision-specific
- production signoff is package-specific
- generated artifacts are content-addressed
- publishing side effects are opt-in and separately authorized
- backtests are chronological
- baseline replay must be reproducible
- learned policy changes are never automatically promoted
