# Affiliate-Mate Learning Loop

v0.7 turns realized channel and affiliate outcomes into an auditable evaluation layer without allowing future data to rewrite the past.

The learning layer is intentionally separate from market evidence, editorial research, and production authorization. It measures what happened after a frozen decision. It does not silently mutate historical forecasts or automatically promote a new scoring policy.

## Trust model

```text
point-in-time evidence
        |
        v
frozen candidate + policy
        |
        v
ForecastSnapshot
        |
        +-------------------------------+
        |                               |
        v                               v
video analytics                  affiliate outcomes
views                           clicks / orders /
                                commission / refunds /
                                reversals
        \                               /
         \                             /
          +---- immutable outcomes ----+
                        |
                        v
             PerformanceReport
                        |
                        v
              CalibrationReport
                        |
                        v
        chronological policy backtest
                        |
                        v
             walk-forward report
                        |
                        v
          HUMAN POLICY DECISION
```

## Why a separate learning store?

Market evidence and realized outcomes have different meanings.

A keyword-demand observation may describe the market at a point in time. A realized affiliate commission is a downstream result of a particular content/offer path and may be reported days later, corrected, refunded, or reversed.

Mixing those records into one generic evidence table would make historical evaluation ambiguous. v0.7 therefore owns a separate SQLite schema namespace.

## Forecast snapshots

`ForecastSnapshot` is the immutable unit of historical prediction truth.

It freezes:

- forecast ID
- product ID
- marketplace and currency
- content ID
- optional production-package digest
- category and price
- `predicted_at`
- explicit outcome horizon
- scoring-policy version and digest
- analysis digest
- complete normalized candidate payload and SHA-256 digest
- whether input completeness was tracked
- available input/evidence fields
- accept/reject decision
- opportunity score
- predicted CTR
- predicted conversion rate
- predicted value per 1,000 views
- commission per sale

The candidate SHA-256 is checked when the object is created. A corrupted or manually edited candidate payload cannot retain an unrelated digest.

A scoring policy must already exist at `predicted_at`. Forecast capture additionally rejects resolved evidence whose `observed_at` is later than `predicted_at`.

## Three outcome clocks

Every realized `OutcomeEvent` preserves three clocks:

### `effective_at`

When the underlying behavior or economic event happened.

### `observed_at`

When the upstream provider made the event/report observable.

### `ingested_at`

When Affiliate-Mate actually learned it.

This distinction is essential for delayed attribution.

Example:

```text
order happened        2026-01-10
affiliate report      2026-01-17
Affiliate-Mate import 2026-01-18
```

A replay evaluated on January 12 cannot use the order. The fact that the order is later attributed back to January 10 does not make it historically knowable.

`LearningStore.list_outcomes(..., as_of=T)` therefore requires both:

```text
observed_at <= T
AND ingested_at <= T
```

## Outcome identity and corrections

The provider-neutral outcome identity is:

```text
source + source_event_id + outcome kind
```

An exact replay is idempotent.

The same identity with changed content is a `LearningConflictError`. Upstream corrections must arrive as new explicit events rather than silently rewriting an earlier event.

Batch imports are transactional: one conflicting event rolls back the entire batch.

## Money semantics

Money is stored as integer minor units.

Examples:

```text
EUR 9.25 -> 925
USD 4.99 -> 499
```

Commission is positive. Refund and reversal records retain positive absolute amounts but expose negative `signed_amount_minor` values for aggregation.

```text
net commission = gross commission - refunds - reversals
```

Mixed currencies are never silently summed. Currency conversion would require an explicit future FX-evidence boundary.

## Lineage

Outcomes are joined through explicit identifiers:

```text
product_id
content_id
optional production package digest
```

Titles are not keys. Affiliate-Mate does not use fuzzy product/video title matching to decide which outcome belongs to which forecast.

If both a forecast and an outcome have production-package digests, conflicting digests fail the performance report.

## Report maturity

A forecast has a declared horizon. Reporting systems may have additional lag.

The default performance policy requires:

```text
evaluated_at >= predicted_at + horizon + 7 days
```

and explicit reports for:

- video views
- affiliate clicks
- orders
- commission

Missing data is not interpreted as zero.

## Observational metrics

For mature, complete forecasts:

```text
CTR              = clicks / views
conversion rate  = orders / clicks
realized EV/1K   = 1000 × net commission / views
```

These metrics describe realized predictive performance. They are not causal estimates of what would have happened under another recommendation.

## Calibration

Calibration groups mature forecasts by:

```text
marketplace × category × price band
```

Price bands are deterministic and versioned in code.

CTR and conversion calibration expose Wilson 95% confidence intervals. Minimum forecast/view/click/order counts prevent tiny cohorts from being treated as reliable calibration evidence.

Drift state is one of:

```text
stable

drift

insufficient
```

No opaque model decides the state.

## Scoring-policy versions

`ScoringPolicyVersion` contains a strict JSON policy payload and deterministic digest.

Versions are immutable. A child policy may reference a parent version, but the parent must already exist and cannot have been created after the child.

The policy registry is provenance, not an active-policy pointer.

## Backtests

A policy change is evaluated against frozen historical candidate payloads.

The main chronological boundary is:

```text
policy.created_at <= train_cutoff
train_cutoff <= forecast.predicted_at < evaluation_end
outcomes must be known by evaluated_at
```

Before comparing policies, Affiliate-Mate replays the stored baseline decision from the frozen candidate. If the current baseline replay does not reproduce the historical accept/reject decision, promotion eligibility is blocked.

That catches reproducibility regressions in scoring/evaluation behavior instead of quietly comparing a challenger against a moving baseline.

Default promotion gates require:

- at least 10 complete evaluation forecasts
- at least 3 challenger-selected forecasts
- zero baseline replay mismatches
- comparable realized currency
- estimable realized EV/1K
- no realized EV/1K regression worse than 5%

These defaults are explicit policy, not universal truth.

## Walk-forward evaluation

A single holdout period may be lucky.

`walk_forward_backtest()` accepts multiple chronological folds. Fold evaluation windows may not move backward or overlap.

Every candidate policy used in a fold must be independently registered and must exist by that fold's training cutoff.

The top-level walk-forward report is promotion-eligible only when every fold passes.

## No automatic promotion

`promotion_eligible=true` is only an evaluation result.

It never changes which scoring policy is active.

A human may append an approve/reject `learning_policy_decisions` event referencing the exact evaluation digest. That audit event is intentionally separate from future operational configuration.

## Versioned machine contracts

v0.7 introduces:

```text
affiliate-mate.outcome-event.v1
affiliate-mate.forecast-snapshot.v1
affiliate-mate.scoring-policy.v1
affiliate-mate.performance-report.v1
affiliate-mate.calibration-report.v1
affiliate-mate.backtest-report.v1
affiliate-mate.walk-forward-report.v1
```

## CLI

The sixth CLI is:

```text
affiliate-mate-learning
```

Commands:

```text
init
policy-register
forecast
import-video
import-affiliate
performance
calibrate
backtest
walk-forward
policy-decision
```

See `docs/EVALUATION_PROTOCOL.md` for the normative evaluation rules and `docs/QUALITY_BAR.md` for repository-wide engineering expectations.
