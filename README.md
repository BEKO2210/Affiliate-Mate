# Affiliate-Mate

**Open-source, evidence-first product opportunity research for affiliate creators.**

Affiliate-Mate does not start by generating a video. It starts by asking a harder question:

> **Which products have enough verifiable economics, demand, competition, and content opportunity to justify deeper research?**

The project is provider-neutral and local-first. Catalog discovery, market intelligence, evidence history, decision gates, scoring, and later content production are deliberately separate layers.

## What Affiliate-Mate is not

Affiliate-Mate is not a "two prompts = passive income" generator, an Amazon scraper, a YouTube scraper, or an auto-publishing spam bot. It makes no income guarantee and does not invent product experience, keyword volume, or commission rates.

Most of the project works without an LLM or cloud account. Live Amazon and YouTube integrations are optional adapters.

## Current status — v0.4 Market Intelligence

v0.4 fills the research boundary that catalog data alone cannot answer:

- supported YouTube Data API v3 competition collector
- deterministic, inspectable competition and content-gap scoring
- user-owned/licensed keyword-demand CSV adapter
- explicit buyer-intent evidence
- trend + seasonality metrics from time-series exports
- signal-specific evidence freshness/TTL rules
- source-level API call budgets
- provider collection health reports
- deterministic JSON replay fixtures
- near-duplicate product clustering before expensive collection
- third CLI: `affiliate-mate-intel`

Previous milestones remain intact:

- v0.1 — transparent opportunity score
- v0.2 — evidence store, hard gates, sensitivity, automation JSON
- v0.3 — Amazon Creators API catalog integration, commission schedules, bounded HTTP

It still performs **no storefront/YouTube HTML scraping, no automatic posting, no LLM content generation, and no invented economics**.

## Architecture in one minute

```text
 Catalog providers                Market evidence providers
 /      |       \                /      |       |       \
mock  Amazon   future         keyword  YouTube  trend   replay
 \      |       /                \      |       |       /
     CatalogItem                  EvidenceObservation
          |                              |
   commission schedule             SQLite history
          |                    provenance + time + expiry
          +---------------+--------------+
                          v
                   ProductCandidate
                          |
                 point-in-time resolution
                          |
                    required hard gates
                          |
               transparent score + sensitivity
                          |
                       shortlist
                          |
                 human research / approval
                          |
                 future production adapters
```

A provider can acquire evidence. It cannot declare a product profitable and cannot bypass the decision engine.

## Quick start

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

The package installs three CLIs:

```text
affiliate-mate          evidence + decision engine
affiliate-mate-catalog  catalog discovery + commission tools
affiliate-mate-intel    market intelligence + replay + clustering
```

## Credential-free market-intelligence run

The repository includes illustrative keyword, trend, and replay fixtures:

```bash
affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --keyword-csv sample_data/keyword_demand.example.csv \
  --trend-csv sample_data/trend_series.example.csv \
  --replay sample_data/market_replay.example.json \
  --format json
```

These fixtures are development data, not current market claims.

Now analyze with the persisted evidence:

```bash
affiliate-mate analyze sample_data/products.csv \
  --evidence-db affiliate-mate.sqlite3 \
  --min-evidence-confidence 0.5 \
  --include-rejected
```

## YouTube market intelligence

Affiliate-Mate uses the supported **YouTube Data API v3**, not HTML scraping. Configure an API key through the environment:

```bash
export YOUTUBE_API_KEY="..."
```

Collect live competition/content-gap evidence:

```bash
affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --youtube \
  --youtube-language de \
  --youtube-max-results 25 \
  --youtube-max-collections 10
```

One landscape uses `search.list` to discover the top videos and `videos.list` to obtain view statistics. The current scoring records its ingredients in observation metadata:

**Competition**

```text
40% median-view strength
25% query-token coverage
20% recent-result share
15% dominant-channel share
```

**Content gap**

```text
45% missing query-token coverage
30% missing review/comparison-format coverage
25% stale-result share
```

These are transparent heuristics over the sampled top results, not a model of YouTube's ranking algorithm.

YouTube announced a granular quota transition for `search.list` in June 2026. Affiliate-Mate therefore exposes an explicit process-local collection budget rather than hiding unlimited search loops behind automation.

See [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md).

## Keyword demand and buyer intent

Affiliate-Mate accepts user-owned or properly licensed exports:

```csv
product_id,marketplace,monthly_searches,buyer_intent,observed_at,source,confidence
```

Both values are explicit. Missing demand or buyer intent is not guessed.

```bash
affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --keyword-csv sample_data/keyword_demand.example.csv
```

## Trend and seasonality

Time-series input is intentionally minimal:

```csv
product_id,marketplace,observed_at,value
```

At least four points are required. v0.4 emits:

- `trend_strength` — recent-half versus prior-half level, neutral around 50
- `seasonality` — coefficient-of-variation intensity

They are **descriptive auxiliary evidence**. v0.4 does not silently inject them into the opportunity score or present them as forecasts.

## Evidence freshness

Market truth ages. Default TTLs are explicit:

| Signal | Default validity |
|---|---:|
| price | 1 day |
| commission rate | 7 days |
| YouTube competition | 7 days |
| content gap | 7 days |
| buyer intent | 14 days |
| trend strength | 14 days |
| monthly search demand | 30 days |
| seasonality / evidence quality | 30 days |

A provider-supplied expiry always wins; generic policy never extends it.

## Collection health and replay

`collect_evidence()` reports each provider as `success`, `empty`, or `failed`. Evidence is rejected when a provider returns a different product or marketplace than requested.

Successful independent evidence may still be persisted if another provider fails. Use `--fail-fast` when a workflow requires all configured providers to succeed.

`ReplayEvidenceProvider` makes captured numeric evidence reproducible without network calls. This is used for deterministic contributor workflows and regression tests, not to bypass normal expiry semantics.

## Near-duplicate clustering

Before spending live API calls, likely variants can be grouped by normalized title-token similarity:

```bash
affiliate-mate-intel cluster sample_data/products.csv \
  --threshold 0.72 \
  --format json
```

Clustering only groups within the same marketplace. It never deletes candidates or merges economics automatically.

## Catalog discovery without credentials

```bash
affiliate-mate-catalog mock-search camera --marketplace DE --format json
```

The mock provider is deterministic and makes no network calls.

## Amazon Creators API

Affiliate-Mate targets Amazon's Creators API rather than new work around legacy PA-API 5.

```bash
export AMAZON_CREATORS_CREDENTIAL_ID="..."
export AMAZON_CREATORS_CREDENTIAL_SECRET="..."
export AMAZON_CREATORS_CREDENTIAL_VERSION="3.2"
export AMAZON_ASSOCIATE_TAG="..."

affiliate-mate-catalog amazon-search camera \
  --marketplace DE \
  --search-index All \
  --limit 10
```

Live access requires valid access granted by Amazon. The project does not automate enrollment.

See [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md).

## Commission schedules are explicit

Affiliate-Mate does **not** ship permanent Amazon commission percentages. Rates can change and may differ by program, marketplace, and category.

```csv
marketplace,category,commission_rate
DE,ExampleElectronics,0.0300
DE,ExampleKitchen,0.0400
*,*,0.0100
```

The repository sample is illustrative, **not a statement of current Amazon rates**.

```bash
affiliate-mate-catalog commission-lookup \
  sample_data/commission_schedule.example.csv \
  DE ExampleElectronics
```

## Evidence and decision engine

Rank normalized candidates:

```bash
affiliate-mate score sample_data/products.csv --top 10
```

Run hard gates, scoring, and sensitivity analysis:

```bash
affiliate-mate analyze sample_data/products.csv --include-rejected
```

Stable machine-readable report:

```bash
affiliate-mate analyze sample_data/products.csv \
  --include-rejected \
  --format json > analysis.json
```

The decision automation contract remains `affiliate-mate.analysis.v1`.

## Local evidence store

```bash
affiliate-mate evidence init affiliate-mate.sqlite3

affiliate-mate evidence add affiliate-mate.sqlite3 demo-gps-1 monthly_searches 4200 \
  --source manual-keyword-check \
  --confidence 0.9 \
  --observed-at 2026-08-25T10:00:00Z

affiliate-mate evidence latest affiliate-mate.sqlite3 demo-gps-1 monthly_searches \
  --as-of 2026-08-25T11:00:00Z \
  --format json
```

Evidence history keeps source, timestamp, marketplace, confidence, optional expiry, unit, and strict JSON metadata. Historical `as_of` evaluation excludes future observations.

## Transparent score

| Component | Weight |
|---|---:|
| Economics / commission per sale | 30% |
| Search demand | 20% |
| Competition opportunity | 20% |
| Buyer intent | 15% |
| Content gap | 10% |
| Evidence quality | 5% |

Base estimated affiliate value per 1,000 views:

```text
1000 × estimated CTR × estimated conversion rate × commission per sale
```

This is an assumption-driven estimate, not a revenue promise. The engine reports a CTR/conversion sensitivity floor/base/ceiling.

## Default rejection policy

| Gate | Default |
|---|---:|
| Commission per sale | ≥ 2.00 |
| Monthly searches | ≥ 100 |
| YouTube competition | ≤ 95 |
| Buyer intent | ≥ 35 |
| Evidence quality | ≥ 40 |
| Estimated value / 1,000 views | ≥ 1.00 |
| Opportunity score | ≥ 45 |

A high weighted score cannot override a failed hard gate.

## Product principles

1. **Evidence before generation.** Research first, content second.
2. **Fail closed on ambiguous critical data.** Missing evidence must not become fake confidence.
3. **Provider-neutral core.** Amazon and YouTube are adapters, not the architecture.
4. **Catalog facts are not market intelligence.** Discovery and judgment remain separate.
5. **Time and provenance survive normalization.** Market evidence expires.
6. **No brittle scraping as a foundation.** Prefer supported APIs and user-owned exports.
7. **No permanent hard-coded commission truth.** Economics come from explicit data.
8. **No hidden unlimited collection.** Retries and source call budgets are bounded.
9. **Auxiliary metrics do not silently alter scoring.** Scoring-policy changes must be explicit.
10. **Human approval before publishing.** Automation assists judgment; it does not erase it.
11. **Original content over mass production.** Repetitive template spam is a non-goal.
12. **Every revenue estimate exposes its assumptions.**

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system boundaries
- [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md) — evidence invariants and storage
- [`docs/DECISION_POLICY.md`](docs/DECISION_POLICY.md) — hard gates and decisions
- [`docs/ANALYSIS_OUTPUT.md`](docs/ANALYSIS_OUTPUT.md) — JSON automation contract
- [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md) — catalog/OAuth contracts
- [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md) — v0.4 signals and collectors
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestones

## Roadmap

v0.4 establishes auditable market intelligence. The next milestone is **v0.5 — Research Workspace**: product briefs, claim/evidence ledgers, user-supplied review clustering, citation-ready notes, research completeness gates, and explicit human approval history.

## Responsible use

Users are responsible for affiliate disclosures, program terms, API/data licenses, product-claim accuracy, and rights to published media. Affiliate-Mate does not guarantee traffic, conversions, commissions, or income.

## License

MIT
