# Affiliate-Mate

**Open-source, evidence-first affiliate research, production planning, and leakage-resistant performance learning.**

Affiliate-Mate is built around a simple trust rule:

> **Automation may collect, rank, draft, render, and learn. It may not silently turn weak evidence into a product claim, reuse stale approval, or learn from future data.**

The project separates discovery, evidence, decisions, research, approval, production, and realized outcomes so no marketplace, model, renderer, publisher, or analytics feed becomes the system's trust root.

## Current status — v0.7 Learning Loop

v0.7 closes the loop between **what Affiliate-Mate predicted** and **what actually happened** without rewriting history:

- immutable point-in-time forecast snapshots
- provider-neutral realized-outcome events
- separate `effective_at`, `observed_at`, and `ingested_at` timestamps
- YouTube/video analytics CSV import
- affiliate click/order/commission/refund/reversal import
- minor-unit money accounting
- explicit product + content + production-package lineage
- delayed-attribution handling
- mature-window performance reports
- CTR, conversion-rate, and value-per-1,000-view calibration
- Wilson 95% intervals for rate metrics
- minimum-sample safeguards
- marketplace/category/price-band cohort reports
- calibration drift detection
- immutable scoring-policy registry
- baseline-replay integrity checks
- chronological holdout backtests
- walk-forward policy evaluation
- hard future-data / target-leakage guards
- append-only human policy decisions
- sixth CLI: `affiliate-mate-learning`

**v0.7 does not auto-promote a scoring policy.** A backtest can produce evidence that a candidate is eligible for review; changing production policy remains an explicit human decision.

Previous trust boundaries remain intact:

- **v0.1** — transparent opportunity score
- **v0.2** — evidence store, hard gates, sensitivity, automation JSON
- **v0.3** — catalog adapters, Amazon Creators API, bounded HTTP, commission schedules
- **v0.4** — YouTube/keyword/trend market intelligence, freshness, replay, budgets
- **v0.5** — claim/evidence ledger, research completeness, approval snapshots
- **v0.6** — grounded production contracts, content-addressed assets, production signoff, publish dry-run

## Architecture

```text
Catalogs + market sources
          |
          v
 Evidence Engine
 provenance + time + expiry
          |
          v
 Opportunity Engine
 hard gates + score + sensitivity
          |
          v
      SHORTLIST
          |
          v
 Research Workspace
 sources + claims + citations + notes
          |
          v
 Research completeness
          |
          v
    HUMAN APPROVAL
          |
          v
 Research snapshot SHA-256
          |
          v
 ProductionAuthorization
          |
          v
 Grounded production package
 script + metadata + assets + lineage
          |
          v
 HUMAN PRODUCTION SIGNOFF
          |
          v
 Publish dry-run / future publisher
          |
          v
 Realized outcomes
 views + clicks + orders + revenue
 refunds + reversals + attribution time
          |
          v
 Learning Store
 immutable forecasts + outcome history
          |
          v
 Calibration / drift / backtest
          |
          v
 HUMAN POLICY DECISION
          |
          +--------------------------+
                                     |
                                     v
                         future scoring policy
```

Two invariants matter most:

1. **History is immutable.** Future outcomes never change what an earlier forecast supposedly knew.
2. **Learning is advisory until reviewed.** Evaluation evidence cannot silently mutate the active policy.

## Quick start

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Affiliate-Mate installs six focused CLIs:

```text
affiliate-mate             evidence + opportunity decision engine
affiliate-mate-catalog     catalog discovery + commission tools
affiliate-mate-intel       market intelligence + replay + clustering
affiliate-mate-research    claims + citations + human approval
affiliate-mate-production  grounded production planning + publish dry-run
affiliate-mate-learning    forecasts + outcomes + calibration + backtests
```

## v0.7 learning workflow

### 1. Initialize the learning schema

The learning tables use their own schema namespace and can coexist with the evidence and research tables in one SQLite database.

```bash
affiliate-mate-learning init affiliate-mate.sqlite3
```

### 2. Register the scoring policy that actually existed

A forecast is invalid if it references a policy that had not yet been registered at prediction time.

```bash
affiliate-mate-learning policy-register affiliate-mate.sqlite3 baseline-v1 \
  --created-at 2026-01-01T00:00:00+00:00 \
  --notes "Production baseline"
```

Policy records are immutable. Replaying an identical record is idempotent; trying to reuse the same version name with different contents is a conflict.

### 3. Freeze a forecast before outcomes exist

```bash
affiliate-mate-learning forecast \
  affiliate-mate.sqlite3 \
  sample_data/products.csv \
  demo-headphones-1 \
  --policy-version baseline-v1 \
  --content-id youtube:demo123 \
  --category audio \
  --predicted-at 2026-01-02T00:00:00+00:00 \
  --horizon-days 30 \
  --evidence-db affiliate-mate.sqlite3 \
  --output forecast.json
```

A forecast snapshot freezes:

```text
candidate values
explicitly available fields
policy version + policy digest
analysis digest
candidate digest
decision + score
predicted CTR
predicted conversion rate
predicted EV/1K
commission per sale
prediction time + outcome horizon
product/content/package lineage
```

If point-in-time evidence resolution contains an observation from after `predicted_at`, forecast capture fails.

### 4. Import realized outcomes

Video analytics:

```bash
affiliate-mate-learning import-video \
  affiliate-mate.sqlite3 \
  sample_data/video_analytics.example.csv \
  --ingested-at 2026-02-10T12:00:00+00:00
```

Affiliate outcomes:

```bash
affiliate-mate-learning import-affiliate \
  affiliate-mate.sqlite3 \
  sample_data/affiliate_outcomes.example.csv \
  --ingested-at 2026-02-12T12:00:00+00:00
```

The import model intentionally keeps three different clocks:

```text
effective_at  when the outcome economically/behaviorally happened
observed_at   when the source reported it
ingested_at   when Affiliate-Mate actually learned it
```

A historical evaluation at time `T` may use an event only if **both** `observed_at <= T` and `ingested_at <= T`. An affiliate conversion attributed to January but first received in February cannot leak into a January backtest.

### 5. Compare forecast vs reality

```bash
affiliate-mate-learning performance \
  affiliate-mate.sqlite3 \
  <forecast-id> \
  --evaluated-at 2026-02-15T00:00:00+00:00 \
  --reporting-lag-days 7
```

The report remains immature until the forecast horizon plus configured reporting lag has passed. It also requires explicit outcome kinds instead of silently interpreting missing rows as zero.

### 6. Calibrate cohorts

```bash
affiliate-mate-learning calibrate \
  affiliate-mate.sqlite3 \
  --start 2026-01-01T00:00:00+00:00 \
  --end 2026-06-01T00:00:00+00:00 \
  --evaluated-at 2026-06-15T00:00:00+00:00 \
  --min-forecasts 5 \
  --min-views 5000 \
  --min-clicks 100 \
  --min-orders 10
```

Calibration is grouped by:

```text
marketplace × category × price band
```

Rate metrics expose Wilson 95% intervals. Cohorts that do not meet minimum evidence are marked insufficient rather than promoted as precise findings.

### 7. Backtest a challenger policy

```bash
affiliate-mate-learning backtest \
  affiliate-mate.sqlite3 \
  baseline-v1 \
  candidate-v2 \
  DE \
  --train-cutoff 2026-04-01T00:00:00+00:00 \
  --evaluation-end 2026-06-01T00:00:00+00:00 \
  --evaluated-at 2026-06-15T00:00:00+00:00
```

The evaluation window is strictly after the training cutoff. Candidate and baseline policies must already have existed at the cutoff. Stored historical baseline decisions are replayed from frozen candidate inputs; any mismatch blocks promotion eligibility.

### 8. Walk forward instead of trusting one lucky split

```bash
affiliate-mate-learning walk-forward \
  affiliate-mate.sqlite3 \
  sample_data/walk_forward_folds.example.json \
  --evaluated-at 2026-06-15T00:00:00+00:00
```

Each fold uses an independently versioned candidate policy. Backwards-overlapping evaluation windows are rejected. A walk-forward report passes only when every fold passes its own promotion gate.

### 9. Record the human policy decision

```bash
affiliate-mate-learning policy-decision \
  affiliate-mate.sqlite3 \
  baseline-v1 \
  candidate-v2 \
  <evaluation-digest> \
  approve \
  --actor reviewer@example \
  --reason "Chronological evaluation passed; change reviewed." \
  --created-at 2026-06-16T00:00:00+00:00
```

This writes an append-only audit event. It **does not** flip an invisible `active_policy` pointer.

## What v0.7 measures

For a mature forecast:

```text
CTR              = clicks / views
conversion rate  = orders / clicks
net commission   = gross commission - refunds - reversals
realized EV/1K   = 1000 × net commission / views
```

Money is stored in integer minor units to avoid floating-point accounting drift.

These are observational performance metrics, not causal estimates. Affiliate-Mate does not claim that a policy caused an outcome merely because the outcome followed it.

## Reproducibility contract

The learning layer uses explicit versioned contracts:

```text
affiliate-mate.outcome-event.v1
affiliate-mate.forecast-snapshot.v1
affiliate-mate.scoring-policy.v1
affiliate-mate.performance-report.v1
affiliate-mate.calibration-report.v1
affiliate-mate.backtest-report.v1
affiliate-mate.walk-forward-report.v1
```

Historical forecast snapshots preserve candidate input, availability tracking, policy identity, and digests. Outcome events preserve source identity and reporting times. Replays are idempotent and conflicting source identities fail closed.

See [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md) for the normative evaluation specification.

## Production trust chain

v0.6 remains the production boundary:

```text
current research approval
        +
approval-bound research digest
        ↓
ProductionAuthorization
        ↓
grounded script
        ↓
content-addressed production package
        ↓
human production signoff
        ↓
publish dry-run
```

A stale approval, unsupported factual segment, replaced artifact, stale package signoff, missing disclosure, missing rendered asset, or side-effecting dry-run publisher blocks readiness.

See [`docs/PRODUCTION_ADAPTERS.md`](docs/PRODUCTION_ADAPTERS.md).

## Quality bar

Affiliate-Mate is intentionally being built as a serious open-source tool rather than a single-use automation script. Every new subsystem should have:

- a documented trust boundary
- a deterministic credential-free path
- explicit versioned machine contracts
- fail-closed validation
- immutable or append-oriented audit history where decisions matter
- tests for adversarial/time-ordering cases
- reproducible examples
- migration/version semantics
- no hidden promotion or side effects

The repository-level quality gates are documented in [`docs/QUALITY_BAR.md`](docs/QUALITY_BAR.md).

## Documentation

| Document | Purpose |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | system boundaries and end-to-end data flow |
| [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md) | normative learning-loop evaluation protocol |
| [`docs/LEARNING_LOOP.md`](docs/LEARNING_LOOP.md) | v0.7 data model, imports, reports, and CLI |
| [`docs/PRODUCTION_ADAPTERS.md`](docs/PRODUCTION_ADAPTERS.md) | v0.6 production trust chain |
| [`docs/APPROVAL_INTEGRITY.md`](docs/APPROVAL_INTEGRITY.md) | revision-bound research approval |
| [`docs/RESEARCH_WORKSPACE.md`](docs/RESEARCH_WORKSPACE.md) | claims, sources, citations, and review |
| [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md) | market evidence providers |
| [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md) | catalog/OAuth boundaries |
| [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md) | evidence storage and time semantics |
| [`docs/DECISION_POLICY.md`](docs/DECISION_POLICY.md) | opportunity hard gates |
| [`docs/ANALYSIS_OUTPUT.md`](docs/ANALYSIS_OUTPUT.md) | analysis JSON contract |
| [`docs/QUALITY_BAR.md`](docs/QUALITY_BAR.md) | repository-wide engineering acceptance bar |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | path to operational hardening and v1.0 |

## Responsible use

Users remain responsible for affiliate disclosures, program terms, API/data licenses, claim accuracy, media rights, generated-content review, privacy obligations, and platform rules.

Affiliate-Mate does not guarantee traffic, conversions, commissions, monetization, or income.

## License

MIT
