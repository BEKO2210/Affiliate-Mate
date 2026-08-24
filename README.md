# Affiliate-Mate

**Open-source, evidence-first product opportunity research for affiliate creators.**

Affiliate-Mate does not start by generating a video. It starts by asking a harder question:

> **Which products have enough verifiable economics, demand, and content opportunity to justify deeper research?**

The project is provider-neutral and local-first. It combines catalog discovery, provenance-aware evidence storage, fail-closed rejection gates, transparent scoring, sensitivity analysis, and stable JSON output for automation.

## What Affiliate-Mate is not

Affiliate-Mate is not a "two prompts = passive income" generator, an Amazon scraper, or an auto-publishing spam bot. It makes no income guarantee and does not invent product experience.

The analysis core and mock catalog work without an LLM, cloud account, or affiliate-network credential.

## Current status — v0.3 Catalog Integrations

v0.3 adds a strict acquisition boundary on top of the v0.2 Evidence Engine:

- provider-neutral `CatalogItem` and `CatalogSearchProvider`
- Amazon Creators API adapter
- OAuth client-credentials token cache with expiry skew
- one bounded authorization refresh on HTTP 401
- marketplace/domain/currency validation
- `SearchItems` and `GetItems` support
- dependency-free JSON HTTP transport
- explicit retry policy for transient HTTP/rate-limit failures
- numeric `Retry-After` handling
- structured transport/API/protocol errors
- explicit user-supplied commission schedules
- deterministic credential-free mock catalog
- separate `affiliate-mate-catalog` CLI
- adapter contract tests that require no live Amazon credentials

It still performs **no HTML scraping, no automatic posting, no LLM calls, and no invented commission rates**.

## Architecture in one minute

```text
       Catalog providers
      /        |         \
 mock     Amazon API    future
      \        |         /
          CatalogItem
              |
       explicit commission
            schedule
              |
      independent research
            signals
              |
              v
      ProductCandidate
              |
       SQLite evidence
   provenance + time + expiry
              |
              v
    point-in-time resolution
              |
              v
 required evidence + hard gates
              |
       +------+------+
       |             |
     reject      transparent score
                    + sensitivity
                         |
                         v
                     shortlist
                         |
                 human research/review
```

A catalog provider discovers facts about products. It does not decide whether a product is a good opportunity.

## Quick start

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

The project installs two CLIs:

```text
affiliate-mate          evidence + decision engine
affiliate-mate-catalog  catalog discovery + commission tools
```

## Try catalog discovery without credentials

The mock provider is deterministic and makes no network calls:

```bash
affiliate-mate-catalog mock-search camera --marketplace DE
```

Machine-readable output:

```bash
affiliate-mate-catalog mock-search camera \
  --marketplace DE \
  --format json
```

The mock catalog is for development and demonstrations only. Its products and economics are not market data.

## Amazon Creators API

Affiliate-Mate targets Amazon's Creators API rather than building new integration work around legacy PA-API 5.

Configure credentials through environment variables only:

```bash
export AMAZON_CREATORS_CREDENTIAL_ID="..."
export AMAZON_CREATORS_CREDENTIAL_SECRET="..."
export AMAZON_CREATORS_CREDENTIAL_VERSION="3.2"
export AMAZON_ASSOCIATE_TAG="..."
```

Then search:

```bash
affiliate-mate-catalog amazon-search camera \
  --marketplace DE \
  --search-index All \
  --limit 10
```

Or emit JSON:

```bash
affiliate-mate-catalog amazon-search camera \
  --marketplace DE \
  --format json
```

Live access requires valid credentials and access granted by Amazon. Affiliate-Mate does not automate Associates/Creators API enrollment.

See [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md) for OAuth, marketplace, retry, parsing, and error-contract details.

## Commission schedules are explicit evidence

Affiliate-Mate does **not** ship permanent Amazon commission percentages. Rates can change and can differ by program, marketplace, and category.

A schedule uses CSV:

```csv
marketplace,category,commission_rate
DE,ExampleElectronics,0.0300
DE,ExampleKitchen,0.0400
*,*,0.0100
```

The repository example is deliberately illustrative test data, **not current Amazon rates**:

```bash
affiliate-mate-catalog commission-lookup \
  sample_data/commission_schedule.example.csv \
  DE ExampleElectronics
```

Rule precedence is exact marketplace/category first, then explicit wildcard fallbacks. Duplicate normalized rules are rejected.

## From catalog item to opportunity candidate

A catalog result is intentionally incomplete. Before it can become a `ProductCandidate`, Affiliate-Mate requires:

- current price
- currency
- commission category
- explicit matching commission rule
- monthly search evidence
- YouTube competition evidence
- buyer-intent evidence
- content-gap evidence
- evidence-quality assessment
- CTR/conversion assumptions

This prevents a catalog API from silently becoming a black-box recommendation system.

## Existing evidence and decision engine

Rank normalized candidates with the original transparent score:

```bash
affiliate-mate score sample_data/products.csv --top 10
```

Run the full evidence-first decision pipeline:

```bash
affiliate-mate analyze sample_data/products.csv --include-rejected
```

Produce stable machine-readable output:

```bash
affiliate-mate analyze sample_data/products.csv \
  --include-rejected \
  --format json > analysis.json
```

The automation contract remains versioned as `affiliate-mate.analysis.v1`.

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

The resolver only applies supported, non-expired observations for the candidate's marketplace. Low-confidence observations can be skipped explicitly. Price evidence with a conflicting currency fails closed instead of being silently converted.

## CSV analysis input

Required columns:

| Column | Meaning |
|---|---|
| `product_id` | Provider-independent product ID |
| `title` | Product title |
| `price` | Current product price |
| `commission_rate` | Decimal rate, e.g. `0.03` for 3% |

Evidence columns used by the default decision policy:

- `monthly_searches`
- `youtube_competition` (0–100, lower is better)
- `buyer_intent` (0–100)
- `content_gap` (0–100)
- `evidence_quality` (0–100)

Model assumptions:

- `estimated_ctr` — default `0.04` if omitted
- `estimated_conversion_rate` — default `0.03` if omitted

For the legacy `score` command, omitted optional fields receive defaults for backward compatibility. `analyze` tracks which fields were explicitly supplied and rejects a candidate when required evidence is missing unless valid persisted evidence fills the gap.

## Transparent score

The score remains inspectable:

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

That number is assumption-driven, not a revenue promise. The engine therefore reports a sensitivity floor/base/ceiling around CTR and conversion assumptions.

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

These are visible starting defaults, not universal truths. Every gate reports actual value, operator, threshold, pass/fail state, and explanation. CLI flags can override numeric thresholds.

## Evidence semantics

Affiliate-Mate treats evidence as time-dependent data:

- every observation has a source and timezone-aware timestamp
- observations may expire
- historical evaluation can use an explicit `as_of`
- future observations are excluded from past evaluations
- expired evidence is excluded by default
- history remains until explicit housekeeping removes it
- confidence filtering is explicit
- provider code acquires evidence; provider code does not decide opportunity quality

See [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md).

## HTTP and provider safety

The live catalog layer uses bounded behavior rather than infinite retries:

- transient statuses can retry
- rate-limit responses can honor `Retry-After`
- exponential backoff is capped
- non-retryable client errors fail immediately
- malformed successful responses are protocol errors
- one 401 can trigger one token refresh
- repeated auth failure is surfaced
- credential secrets are not included in exception text
- marketplace currency mismatch fails closed

All transport behavior is injectable for deterministic tests; CI does not need live Amazon credentials.

## Automation contract

`affiliate-mate analyze --format json` emits:

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
2. **Fail closed on ambiguous critical data.** Missing evidence must not become fake confidence.
3. **Provider-neutral core.** Amazon is an adapter, not the architecture.
4. **Catalog facts are not market intelligence.** Discovery and judgment remain separate.
5. **Time and provenance survive normalization.** Price, demand, and competition change.
6. **No brittle scraping as a foundation.** Prefer supported APIs and user-owned exports.
7. **No permanent hard-coded commission truth.** Economics come from explicit user data.
8. **Human approval before publishing.** Automation assists judgment; it does not erase it.
9. **Original content over mass production.** Repetitive template spam is a non-goal.
10. **Every revenue estimate exposes its assumptions.**
11. **Local-first where practical.** Core analysis works without cloud services.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system boundaries
- [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md) — evidence invariants and storage
- [`docs/DECISION_POLICY.md`](docs/DECISION_POLICY.md) — hard gates and decisions
- [`docs/ANALYSIS_OUTPUT.md`](docs/ANALYSIS_OUTPUT.md) — JSON automation contract
- [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md) — v0.3 provider contracts
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestones

## Roadmap

v0.3 establishes catalog acquisition. The next milestone is **v0.4 — Market Intelligence**: YouTube competition, keyword demand, trend/seasonality signals, content-gap evidence, clustering, and signal-specific freshness policies.

## Responsible use

Users are responsible for affiliate disclosures, program terms, API/data licenses, product-claim accuracy, and rights to published media. Affiliate-Mate does not guarantee traffic, conversions, commissions, or income.

## License

MIT
