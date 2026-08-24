# Affiliate-Mate

**Open-source, evidence-first product opportunity research for affiliate creators.**

Affiliate-Mate does not start by generating a video. It starts by asking a more useful question:

> **Which products have enough evidence, economics, demand, and content opportunity to justify deeper research?**

The project is provider-neutral and local-first. It combines transparent scoring, fail-closed rejection gates, sensitivity analysis, provenance-aware evidence storage, and stable JSON output that other automation can consume.

## What Affiliate-Mate is not

Affiliate-Mate is not a "two prompts = passive income" generator, an Amazon scraper, or an auto-publishing spam bot. It makes no income guarantee and does not invent product experience. The core is deliberately useful without an LLM, a cloud account, or an affiliate-network credential.

## Current status — v0.2 Evidence Engine

The v0.2 milestone adds the first durable decision layer:

- provider-neutral `CandidateProvider` and `EvidenceProvider` protocols
- local SQLite evidence store
- source provenance, marketplace, observation time, confidence, unit, metadata, and expiry
- point-in-time evidence resolution (`as_of`)
- fail-closed required-evidence gate for CSV analysis
- configurable hard rejection gates
- deterministic score explanations
- 3x3 CTR/conversion sensitivity grid
- versioned JSON automation output (`affiliate-mate.analysis.v1`)
- CLI commands for evidence init/add/latest
- optional enrichment of CSV candidates from the evidence database
- deterministic tests and GitHub Actions CI

It still performs **no scraping, no automatic posting, and no LLM calls**.

## Architecture in one minute

```text
Catalog / CSV / future APIs
          |
          v
    Normalized candidate
          |
          +-----------------------+
          |                       |
          v                       v
 Evidence providers        Direct input evidence
          |                       |
          +----------+------------+
                     v
              SQLite evidence store
          provenance + time + expiry
                     |
                     v
           point-in-time resolution
                     |
                     v
        required evidence + hard gates
                     |
             +-------+-------+
             |               |
           reject         transparent score
                             + sensitivity
                                  |
                                  v
                              shortlist
                                  |
                          human research/review
```

Content-generation and publishing adapters stay downstream of this decision boundary.

## Quick start

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Rank candidates with the original transparent score:

```bash
affiliate-mate score sample_data/products.csv --top 10
```

Run the full v0.2 decision pipeline:

```bash
affiliate-mate analyze sample_data/products.csv --include-rejected
```

Produce stable machine-readable output:

```bash
affiliate-mate analyze sample_data/products.csv \
  --include-rejected \
  --format json > analysis.json
```

## Local evidence store

Initialize a database:

```bash
affiliate-mate evidence init affiliate-mate.sqlite3
```

Append an observation:

```bash
affiliate-mate evidence add affiliate-mate.sqlite3 demo-gps-1 monthly_searches 4200 \
  --source manual-keyword-check \
  --confidence 0.9 \
  --observed-at 2026-08-25T10:00:00Z
```

Read the latest valid observation:

```bash
affiliate-mate evidence latest affiliate-mate.sqlite3 demo-gps-1 monthly_searches \
  --as-of 2026-08-25T11:00:00Z \
  --format json
```

Use stored evidence while analyzing candidates:

```bash
affiliate-mate analyze sample_data/products.csv \
  --evidence-db affiliate-mate.sqlite3 \
  --as-of 2026-08-25T11:00:00Z \
  --min-evidence-confidence 0.5 \
  --include-rejected
```

The resolver only applies supported, non-expired observations for the candidate's marketplace. Low-confidence observations can be skipped explicitly. Price evidence with a currency that conflicts with the candidate fails closed instead of silently converting it.

## CSV input

Required columns:

| Column | Meaning |
|---|---|
| `product_id` | Provider-independent product ID |
| `title` | Product title |
| `price` | Current product price |
| `commission_rate` | Decimal rate, e.g. `0.03` for 3% |

Evidence columns used by the default v0.2 policy:

- `monthly_searches`
- `youtube_competition` (0–100, lower is better)
- `buyer_intent` (0–100)
- `content_gap` (0–100)
- `evidence_quality` (0–100)

Model assumptions:

- `estimated_ctr` — default `0.04` if omitted
- `estimated_conversion_rate` — default `0.03` if omitted

For the legacy `score` command, omitted optional fields still receive defaults for backward compatibility. The v0.2 `analyze` command tracks which fields were explicitly supplied and rejects a candidate when required evidence is missing, unless valid persisted evidence fills the gap.

## Transparent score

The score remains intentionally inspectable:

| Component | Weight |
|---|---:|
| Economics / commission per sale | 30% |
| Search demand | 20% |
| Competition opportunity | 20% |
| Buyer intent | 15% |
| Content gap | 10% |
| Evidence quality | 5% |

The base estimated affiliate value per 1,000 views is:

```text
1000 × estimated CTR × estimated conversion rate × commission per sale
```

That number is an assumption-driven estimate, not a revenue promise. v0.2 therefore reports a sensitivity floor/base/ceiling around the CTR and conversion assumptions instead of presenting a single estimate as certainty.

## Default rejection policy

The default policy is deliberately visible and configurable:

| Gate | Default |
|---|---:|
| Commission per sale | ≥ 2.00 |
| Monthly searches | ≥ 100 |
| YouTube competition | ≤ 95 |
| Buyer intent | ≥ 35 |
| Evidence quality | ≥ 40 |
| Estimated value / 1,000 views | ≥ 1.00 |
| Opportunity score | ≥ 45 |

These are starting defaults, not universal truths. Every gate appears in the decision report with the actual value, operator, threshold, pass/fail state, and explanation. CLI flags can override the numeric thresholds.

## Evidence semantics

Affiliate-Mate treats evidence as time-dependent data, not permanent truth:

- every observation has a source and timezone-aware timestamp
- observations may expire
- queries can be evaluated at an explicit historical `as_of` instant
- expired evidence is excluded by default
- history is retained until explicit housekeeping deletes it
- confidence filtering is explicit
- provider code collects evidence; it does not decide whether a product is good

See [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md) for invariants and schema details.

## Automation contract

`affiliate-mate analyze --format json` emits a versioned payload containing:

- policy used
- shortlist/reject summary
- normalized product values
- explicitly provided fields
- every gate result and rejection reason
- score breakdown and explanations
- sensitivity grid
- applied and skipped persisted evidence

See [`docs/ANALYSIS_OUTPUT.md`](docs/ANALYSIS_OUTPUT.md).

## Product principles

1. **Evidence before generation.** Research first, content second.
2. **Fail closed on ambiguous critical data.** Missing evidence should not become fake confidence.
3. **Provider-neutral core.** Amazon is an adapter, not the architecture.
4. **Time and provenance survive normalization.** Price, demand, and competition change.
5. **No brittle scraping as a foundation.** Prefer supported APIs and user-owned exports.
6. **Human approval before publishing.** Automation should assist judgment, not erase it.
7. **Original content over mass production.** Repetitive template spam is a non-goal.
8. **Every revenue estimate exposes its assumptions.**
9. **Local-first where practical.** Core analysis works without cloud services.

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

The next milestone is **v0.3 — Catalog Integrations**: supported catalog adapters, marketplace-aware currency handling, commission schedules, rate limiting, retries, and a credential-free mock provider for contributors.

## Responsible use

Users are responsible for affiliate disclosures, platform policies, product-data licenses, product-claim accuracy, and the rights to any media they publish. Affiliate-Mate does not guarantee traffic, conversions, commissions, or income.

## License

MIT
