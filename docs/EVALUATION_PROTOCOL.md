# Evaluation Protocol

This document is the normative evaluation protocol for Affiliate-Mate's learning layer. It is written as a reproducibility contract, not marketing copy.

## 1. Objective

Affiliate-Mate estimates whether deeper research and production effort is justified for a product opportunity. v0.7 evaluates whether those assumptions are calibrated against later observed outcomes and whether a proposed scoring-policy change improves selection quality out of sample.

No report establishes causal impact. The system measures predictive calibration and historical selection performance.

## 2. Unit of analysis

The primary unit is an immutable `ForecastSnapshot` bound to:

```text
product_id
marketplace
content_id
predicted_at
horizon_days
policy_version
candidate_digest
analysis_digest
```

When available, `package_digest` further binds the forecast to a production artifact lineage.

## 3. Temporal semantics

Three times must not be conflated:

- event/effective time: when performance is attributed,
- observation time: when an upstream source exposed the result,
- ingestion time: when Affiliate-Mate acquired it.

For an evaluation cutoff `T`, an outcome is eligible only if:

```text
observed_at <= T
AND
ingested_at <= T
```

This rule prevents delayed conversions from leaking backwards into an earlier simulated state.

## 4. Forecast freeze

A forecast must be generated using an explicit `predicted_at`.

If persisted evidence is present, every evidence observation carried by the analysis result must satisfy:

```text
evidence.observed_at <= predicted_at
```

The candidate payload and analysis result are hashed at freeze time.

## 5. Outcome window

For a forecast at time `t0` with horizon `H`, effective outcomes are selected from:

```text
[t0, t0 + H)
```

A report is considered mature only after:

```text
t0 + H + reporting_lag
```

The lag is configurable and reported.

## 6. Money

Financial outcomes are stored in integer minor units.

Gross commission, refund, and reversal remain separate event kinds:

```text
net = gross - refunds - reversals
```

A report refuses to combine multiple currencies without explicit FX evidence. v0.7 does not perform implicit FX conversion.

## 7. Calibration estimands

### CTR

```text
realized_ctr = total affiliate clicks / total video views
predicted_ctr = sum(views_i * predicted_ctr_i) / total views
```

### Conversion rate

```text
realized_conversion = total orders / total affiliate clicks
predicted_conversion =
    sum(clicks_i * predicted_conversion_i) / total affiliate clicks
```

### Realized affiliate value per 1,000 views

```text
realized_ev_1k = net commission major-units * 1000 / total views
```

Predicted EV/1K is view-weighted across the cohort.

## 8. Uncertainty

CTR and conversion rate use Wilson score 95% intervals.

A drift state is not emitted until configured minimum samples are met. Below those thresholds, the result is `insufficient`.

The current money calibration does not claim a parametric confidence interval because transaction-value distributions can be strongly non-normal. A future version may add bootstrap intervals once deterministic resampling and sample-size rules are specified.

## 9. Cohorts

Default calibration cohorts are:

```text
marketplace × category × price band
```

Price bands:

```text
< 50
50–99
100–249
250–499
>= 500
```

Cohorts are descriptive slices. Small cohorts remain `insufficient`.

## 10. Policy backtest

A candidate policy is evaluated only after an explicit training cutoff.

Required chronology:

```text
baseline_policy.created_at <= train_cutoff
candidate_policy.created_at <= train_cutoff
train_cutoff < forecast.predicted_at < evaluation_end
evaluation_end <= evaluated_at
```

The evaluation cohort must have been generated under the declared baseline policy.

## 11. Baseline replay check

The stored historical baseline decision is re-evaluated from the frozen candidate payload. Any mismatch is surfaced.

By default, a baseline replay mismatch blocks promotion eligibility because it indicates code drift, corrupted history, or an incomplete snapshot.

## 12. Promotion gate

A backtest can return `promotion_eligible=true` only when all configured gates pass.

That boolean is advisory. v0.7 has no mechanism that automatically activates a candidate policy.

A human decision can be appended to the policy-decision audit table with:

```text
baseline_version
candidate_version
evaluation_digest
approve | reject
actor
reason
created_at
```

The decision still does not mutate historical forecasts.

## 13. Walk-forward evaluation

A walk-forward plan consists of independent folds. Each fold names a baseline and candidate policy version that existed by that fold's training cutoff.

This avoids the common mistake of evaluating one policy that was tuned using information from the same future interval it is supposed to predict.

## 14. Reproducibility

Machine-readable contracts are versioned:

```text
affiliate-mate.outcome-event.v1
affiliate-mate.forecast-snapshot.v1
affiliate-mate.scoring-policy.v1
affiliate-mate.performance-report.v1
affiliate-mate.calibration-report.v1
affiliate-mate.backtest-report.v1
affiliate-mate.walk-forward-report.v1
```

Policy, candidate, analysis, performance, calibration, and backtest payloads are content-addressable with deterministic SHA-256 serialization where applicable.

## 15. Explicit non-claims

The evaluation layer does not prove:

- causality,
- future platform behavior,
- stable affiliate commission schedules,
- stable search demand,
- that one content format caused a sale,
- that a small cohort generalizes,
- that a policy should be deployed merely because a point estimate improved.
