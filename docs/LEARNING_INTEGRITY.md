# Learning Integrity Hardening — v0.7.1

v0.7.1 is a correctness patch for the v0.7 learning loop. It does not add a new learning algorithm. It closes ambiguity that could otherwise make a historical evaluation look more precise than the underlying data allows.

## 1. Currency minor units are explicit

Realized money is stored as integer minor units, but not every currency uses two decimal places. Affiliate-Mate therefore converts money through an explicit currency exponent table rather than dividing every amount by 100.

Examples:

```text
EUR 925 minor units -> 9.25 EUR
USD 499 minor units -> 4.99 USD
JPY 1500 minor units -> 1500 JPY
```

Unknown currencies fail closed until a minor-unit exponent is explicitly added. This prevents a syntactically valid three-letter code from silently corrupting EV/1K calculations.

The current mapping is intentionally limited to currencies supported by the catalog marketplace layer.

## 2. Aggregate count windows cannot overlap silently

Video views, affiliate clicks, and orders are treated as count aggregates over explicit reporting windows.

Two snapshots from the same source and same metric may be summed only when their windows do not overlap. Touching half-open windows are allowed:

```text
[Jan 1, Jan 2) + [Jan 2, Jan 3)  -> allowed
[Jan 1, Jan 3) + [Jan 2, Jan 3)  -> rejected
```

The second case is dangerous because cumulative or repeated exports can otherwise double-count activity while still looking internally consistent.

Affiliate-Mate does not guess whether overlapping snapshots are cumulative, incremental, or corrected. Ambiguity is an error.

## 3. Production-package lineage is strict when present

If a forecast is bound to a production-package SHA-256 digest, every realized outcome used for that forecast must carry the same digest.

A missing digest is not treated as equivalent to the expected digest.

This prevents a result from being attributed to a reviewed production package merely because product and content identifiers happen to match.

## 4. Counterfactual observability is a promotion gate

A historical policy comparison has a subtle failure mode:

1. the challenger would have selected an item,
2. that item has no mature/complete realized outcome,
3. the item disappears from the evaluated sample,
4. the challenger is judged only on the remaining observable winners.

That is survivorship through missing counterfactual outcomes.

Backtest contract v2 therefore records:

```text
baseline_unobservable_selections
candidate_unobservable_selections
```

The default `BacktestPolicy` requires both counts to be zero before `promotion_eligible=true` is possible.

This is stricter than simply reporting the number of incomplete forecasts. It asks whether missingness is correlated with the actual selection behavior being evaluated.

## 5. Contract versioning

The backtest output shape and promotion semantics changed, so the affected machine contracts advance explicitly:

```text
affiliate-mate.backtest-report.v2
affiliate-mate.walk-forward-report.v2
```

Outcome, forecast, performance, and calibration contracts remain at v1 because their serialized shapes did not change.

## 6. Security/correctness posture

v0.7.1 keeps the same core rule as the rest of Affiliate-Mate:

> If the system cannot prove that two values are comparable, observable, and correctly attributed, it must not manufacture comparability through a permissive default.

These checks are intentionally deterministic, credential-free, and covered by adversarial tests.
