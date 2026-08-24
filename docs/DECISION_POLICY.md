# Decision policy

Affiliate-Mate separates **scoring** from **eligibility**. A score answers "how strong are the measured signals?" A gate answers "is this candidate sufficiently evidenced and economically plausible to spend more research time on?"

## Default gates

| Code | Rule | Default |
|---|---|---:|
| `required_evidence` | required CSV/store signals explicitly present | 5 fields |
| `commission_per_sale` | minimum commission economics | ≥ 2.00 |
| `monthly_searches` | minimum demand | ≥ 100 |
| `youtube_competition` | maximum competition | ≤ 95 |
| `buyer_intent` | minimum commercial intent | ≥ 35 |
| `evidence_quality` | minimum confidence proxy | ≥ 40 |
| `estimated_value_per_1000_views` | minimum base economics | ≥ 1.00 |
| `opportunity_score` | minimum aggregate score | ≥ 45 |

These thresholds are defaults for triage, not claims about universal profitability. They are intentionally configurable from the CLI and serialized into every automation payload.

## Why hard gates exist

A weighted score can hide a fatal weakness. For example, enormous search demand could compensate numerically for near-zero commission economics. Hard gates prevent one strong signal from laundering an unacceptable one.

## Why missing evidence is a gate

The v0.1 CSV model used defaults for optional fields to keep the first CLI simple. That is still supported by `score`. For the decision pipeline, however, a default value must not masquerade as an observation. `analyze` therefore tracks explicit fields and rejects missing required evidence unless the evidence store supplies it.

## No automatic publishing decision

Passing every gate means "worth deeper research," not "publish this." Product claims, user value, media rights, affiliate disclosure, and editorial quality remain downstream human-review concerns.
