# Market Intelligence

v0.4 turns Affiliate-Mate's missing research fields into explicit evidence-provider jobs. The core rule remains unchanged: a provider may collect evidence, but it may not decide that a product is a good opportunity.

## Signals

The first market-intelligence layer distinguishes decision inputs from auxiliary context:

| Signal | Producer | Used by current decision engine | Default TTL |
|---|---|---:|---:|
| `monthly_searches` | keyword CSV/export | yes | 30 days |
| `buyer_intent` | keyword CSV/export | yes | 14 days |
| `youtube_competition` | YouTube Data API | yes | 7 days |
| `content_gap` | YouTube Data API | yes | 7 days |
| `trend_strength` | trend time-series export | auxiliary | 14 days |
| `seasonality` | trend time-series export | auxiliary | 30 days |

Auxiliary signals are stored with the same provenance and point-in-time semantics but are not silently folded into the v0.2 scoring formula. A later scoring-policy change must be explicit and backtestable.

## YouTube competition collector

`YouTubeDataAPIClient` uses the supported YouTube Data API v3 rather than HTML scraping. One collection performs:

1. `search.list` with `part=snippet`, `type=video`, and relevance ordering.
2. `videos.list` for view statistics of the returned video IDs.
3. deterministic landscape scoring over the returned top results.

The collector records the query, result count, median views, query-token coverage, fresh-result share, intent-format share, and dominant-channel share in observation metadata.

The competition score is deliberately inspectable:

```text
40% median-view strength
25% query-token coverage
20% share of results published in the last 365 days
15% dominant-channel share
```

The content-gap score is also explicit:

```text
45% missing query-token coverage
30% missing review/comparison-format coverage
25% stale-result share
```

These scores describe the sampled top-result landscape. They are not a claim to know YouTube's ranking algorithm and are not a substitute for actual conversion data.

### Quota awareness

YouTube announced in June 2026 that `search.list` is moving to its own granular quota bucket. Affiliate-Mate therefore keeps the number of search calls explicit and configurable rather than hiding high-volume collection behind an automatic loop.

Official references:

- https://developers.google.com/youtube/v3/docs/search/list
- https://developers.google.com/youtube/v3/docs/videos/list
- https://developers.google.com/youtube/v3/revision_history

Set the API key only through the environment:

```bash
export YOUTUBE_API_KEY="..."
```

The key is used as a request parameter because that is how the Data API authenticates API-key requests. The project's HTTP exceptions do not include the request URL, preventing the key from being echoed in normal error text.

## Keyword demand

Affiliate-Mate intentionally does not pretend that a free universal keyword-volume API exists. v0.4 accepts user-owned or properly licensed exports with this schema:

```csv
product_id,marketplace,monthly_searches,buyer_intent,observed_at,source,confidence
```

Both demand and buyer intent must be explicit. Missing values are rejected rather than guessed.

Example:

```bash
affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --keyword-csv sample_data/keyword_demand.example.csv
```

## Trend and seasonality

Trend imports use a minimal time-series schema:

```csv
product_id,marketplace,observed_at,value
```

At least four points are required. The current deterministic metrics are:

- `trend_strength`: recent-half mean versus prior-half mean, mapped to 0-100 around neutral 50
- `seasonality`: coefficient of variation, capped at 100

These are descriptive statistics, not forecasts. They are stored as auxiliary evidence and do not alter the core opportunity score in v0.4.

## Freshness policy

`SignalFreshnessPolicy` attaches an expiry only when a provider did not already supply one. Existing explicit expiries always win.

This preserves an important invariant: the producer that knows a datum has a shorter validity window can tighten freshness; a generic policy may not silently extend it.

## Collection-run reports

`collect_evidence()` records one status per provider:

- `success`: provider returned valid observations
- `empty`: provider completed but had no evidence for the candidate
- `failed`: provider raised or returned evidence scoped to the wrong product/marketplace

Successful observations can still be stored when an unrelated provider fails. `--fail-fast` is available for workflows that require all providers to succeed.

Every returned observation is validated against the requested product and marketplace before persistence. This prevents a buggy adapter from contaminating another product's evidence history.

## Replay fixtures

`ReplayEvidenceProvider` loads captured numeric observations from JSON and makes no network calls. It exists for:

- deterministic CI
- reproducing scoring decisions
- provider regression tests
- contributor demos without credentials

Replay is not a bypass around freshness. If a fixture contains an expiry, normal evidence-store rules still apply.

## Near-duplicate clustering

`cluster_candidates()` uses normalized title-token Jaccard similarity and only clusters within the same marketplace. It uses transitive union-find grouping, so variant families can be collapsed before expensive provider collection.

Clustering is advisory. It does not delete candidates and does not merge economics automatically.

## Security and data-rights boundaries

- no YouTube HTML scraping
- no hidden browser automation
- no API keys committed to the repository
- no keyword-volume fabrication
- no automatic copying of third-party review text
- no provider output can bypass the evidence store or hard decision gates
- users remain responsible for rights and terms governing imported datasets

## Example credential-free collection

```bash
affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --keyword-csv sample_data/keyword_demand.example.csv \
  --trend-csv sample_data/trend_series.example.csv \
  --replay sample_data/market_replay.example.json \
  --format json
```

Live YouTube evidence can be added explicitly:

```bash
affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --youtube \
  --youtube-language de \
  --youtube-max-results 25
```

The next milestone should build a research workspace on top of these auditable signals rather than jumping directly to content generation.
