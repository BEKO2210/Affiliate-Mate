# Affiliate-Mate

**Open-source product opportunity research for affiliate creators.**

Affiliate-Mate is not a "two prompts = passive income" generator. Its first job is
to answer a harder question:

> **Which products are actually worth researching and making a useful review about?**

The project ranks product opportunities using transparent economics, demand,
competition, buyer intent, content gaps, and evidence quality. It is designed as
a provider-neutral foundation that can later connect to affiliate networks,
keyword sources, review-analysis tools, LLMs, and publishing workflows.

## Why this exists

A weak automation pipeline starts with a product and immediately generates
content. Affiliate-Mate starts one step earlier:

```text
catalog -> normalize -> evidence -> score -> shortlist -> human review
                                      |
                                      +-> reject weak opportunities early
```

The goal is to spend research and production time only where there is a credible
opportunity to create original, useful content.

## Current status

`v0.1.0` is a deliberately small foundation:

- provider-neutral product model
- transparent 0-100 opportunity score
- estimated commission per sale
- estimated affiliate value per 1,000 views
- CSV import
- CLI ranking
- deterministic tests
- GitHub Actions CI

It performs **no scraping, no automatic posting, and no LLM calls**.

## Quick start

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

python -m pip install -e ".[dev]"
affiliate-mate score sample_data/products.csv --top 10
```

## Input format

The minimal required CSV columns are:

| Column | Meaning |
|---|---|
| `product_id` | Provider-independent ID |
| `title` | Product title |
| `price` | Current product price |
| `commission_rate` | Decimal rate, e.g. `0.03` for 3% |

Optional evidence columns:

- `monthly_searches`
- `youtube_competition` (0-100, lower is better)
- `buyer_intent` (0-100)
- `content_gap` (0-100)
- `evidence_quality` (0-100)
- `estimated_ctr`
- `estimated_conversion_rate`

## Scoring model

The default opportunity score is intentionally inspectable:

| Component | Weight |
|---|---:|
| Economics / commission per sale | 30% |
| Search demand | 20% |
| Competition opportunity | 20% |
| Buyer intent | 15% |
| Content gap | 10% |
| Evidence quality | 5% |

No hidden model decides the score. Every input and weight can be audited.

`estimated_value_per_1000_views` is an **estimate**, not an income promise:

```text
1000 × estimated CTR × estimated conversion rate × commission per sale
```

## Product principles

1. **Evidence before generation.** Research first, content second.
2. **Provider-neutral core.** Amazon is one adapter, not the architecture.
3. **No brittle scraping as a foundation.** Prefer official APIs and user-owned data.
4. **Human approval before publishing.** Automation should assist judgment, not erase it.
5. **Original content over mass production.** Repetitive template spam is a non-goal.
6. **Every revenue estimate shows its assumptions.**
7. **Local-first where practical.** The core engine works without cloud services.

## Planned architecture

```text
Sources
  |-- CSV / manual
  |-- Amazon Creators API adapter
  |-- other affiliate-network adapters
  |-- keyword / trend sources
  `-- YouTube competition signals
          |
          v
Normalization -> Evidence Store -> Opportunity Engine
                                      |
                                      +-> shortlist
                                      +-> rejection reasons
                                      +-> sensitivity analysis
                                      v
                              Research Workspace
                                      |
                            human approval checkpoint
                                      |
                       Script / Video / Publish adapters
```

Amazon's legacy PA-API 5 has been deprecated in favor of the **Creators API**,
so future Amazon integration will target the supported API rather than build new
code around PA-API 5.

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

The next milestone is **v0.2 — Evidence Engine**: provider interfaces, local SQLite
storage, rejection reasons, sensitivity analysis, and a first official catalog
adapter.

## Responsible use

Affiliate-Mate is tooling for research and workflow automation. Users are
responsible for affiliate disclosures, platform policies, product-data licenses,
and the accuracy of claims in published content.

The project does not guarantee traffic, conversions, commissions, or income.

## License

MIT
