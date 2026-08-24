# Catalog Integrations

Affiliate-Mate v0.3 adds catalog discovery without allowing a catalog provider to become the decision engine.

The boundary is deliberate:

```text
catalog provider
      |
      v
  CatalogItem
      |
      +----> commission schedule
      |
      +----> independent market/research signals
      |
      v
ProductCandidate
      |
      v
existing evidence + decision pipeline
```

A catalog can tell Affiliate-Mate what a product is, its current catalog price, marketplace, product URL, brand, and category. It does **not** get to invent search demand, buyer intent, competition, evidence quality, CTR, conversion rate, or commission economics.

## Provider contract

`CatalogSearchProvider` exposes a narrow search interface:

```python
provider.search("camera", marketplace="DE", limit=10)
```

It returns normalized `CatalogItem` records. The core remains independent of Amazon-specific response objects.

Critical values fail closed:

- a discovered item with no current price cannot be promoted to a scored candidate
- a discovered item with no currency cannot be promoted
- a discovered item with no commission category cannot be promoted
- Amazon price currency must agree with the configured marketplace currency
- an unknown commission category must have an explicit schedule rule or wildcard

No silent currency conversion is performed.

## Amazon Creators API

The live Amazon adapter targets **Creators API**, not the deprecated Product Advertising API 5.0.

The implementation follows the supported OAuth client-credentials flow and keeps credentials out of repository files. The required environment variables are:

```bash
export AMAZON_CREATORS_CREDENTIAL_ID="..."
export AMAZON_CREATORS_CREDENTIAL_SECRET="..."
export AMAZON_CREATORS_CREDENTIAL_VERSION="3.2"
export AMAZON_ASSOCIATE_TAG="..."
```

Do not commit these values. `.env.example` only documents variable names.

Credential versions map to Amazon OAuth endpoints:

| Credential version | Region family | Token endpoint |
|---|---|---|
| `3.1` | North America | `https://api.amazon.com/auth/o2/token` |
| `3.2` | Europe | `https://api.amazon.co.uk/auth/o2/token` |
| `3.3` | Far East | `https://api.amazon.co.jp/auth/o2/token` |

The adapter currently exposes:

- `SearchItems` through `AmazonCreatorsClient.search_items`
- `GetItems` through `AmazonCreatorsClient.get_items`
- high-level `AmazonCatalogProvider.search`

Catalog calls are sent to the Creators API catalog base and include the bearer token, partner tag, marketplace domain, requested resources, and marketplace header.

## Token handling

Access tokens are cached in memory until shortly before expiry. Token state is guarded by a lock so concurrent callers do not intentionally refresh the same token at the same time.

A catalog request that receives HTTP `401` performs exactly one credential refresh cycle and retries once. Repeated authorization failure is surfaced to the caller rather than looped indefinitely.

Credential IDs and secrets use `repr=False` in the credential dataclass and are never included in structured exception messages.

## HTTP retries and rate limits

`JsonHttpClient` is dependency-free and has injectable transport/sleep functions so retry behavior can be tested without real network access.

Default transient HTTP statuses:

- `408`
- `425`
- `429`
- `500`
- `502`
- `503`
- `504`

Default behavior:

- at most 4 attempts
- exponential backoff starting at 0.5 seconds
- maximum sleep of 8 seconds
- numeric `Retry-After` is honored when supplied
- non-retryable 4xx responses fail immediately
- malformed JSON is a protocol error

The retry policy is intentionally bounded. Affiliate-Mate must not turn a provider outage or quota problem into an infinite request loop.

## Provider error taxonomy

The catalog layer distinguishes failure classes so callers can decide whether a failure is retryable, configuration-related, or a provider-contract violation:

| Error | Meaning |
|---|---|
| `TransportError` | Network/transport failed before a usable HTTP response |
| `HttpRequestError` | HTTP status remained unsuccessful after transport policy |
| `JsonProtocolError` | Successful HTTP response was not valid object-root JSON |
| `AmazonCreatorsError` | Amazon returned a structured API/auth/catalog error |
| `AmazonCreatorsProtocolError` | Response shape or critical catalog semantics were invalid |
| `ValueError` | Local configuration/input violated an explicit contract |

The adapter does not convert these failures into fake products or guessed values.

## Marketplace and currency semantics

The Amazon adapter maps supported marketplace codes to Amazon domains and expected ISO 4217 currencies. Examples:

| Marketplace | Amazon domain | Expected currency |
|---|---|---|
| `DE` | `www.amazon.de` | `EUR` |
| `UK` | `www.amazon.co.uk` | `GBP` |
| `US` | `www.amazon.com` | `USD` |
| `JP` | `www.amazon.co.jp` | `JPY` |
| `CA` | `www.amazon.ca` | `CAD` |

The full mapping lives in `amazon_creators.py`. If a live response returns a price currency inconsistent with the selected marketplace, parsing fails closed.

This is preferable to silently mixing economics from different marketplaces.

## Commission schedules

Affiliate commission rates are **not hard-coded** into Affiliate-Mate. Rates and program rules change, can differ by market/category, and belong to the user's evidence/configuration layer.

A schedule is supplied as CSV:

```csv
marketplace,category,commission_rate
DE,ExampleElectronics,0.0300
DE,ExampleKitchen,0.0400
*,*,0.0100
```

Values in the example file are illustrative test data, **not current Amazon commission rates**.

Lookup precedence is:

1. exact marketplace + exact category
2. exact marketplace + `*`
3. `*` + exact category
4. `*` + `*`

Duplicate normalized rules are rejected.

You can inspect a schedule rule with:

```bash
affiliate-mate-catalog commission-lookup \
  sample_data/commission_schedule.example.csv \
  DE ExampleElectronics
```

## Credential-free mock provider

Contributors should be able to develop and test Affiliate-Mate without an Amazon account.

```bash
affiliate-mate-catalog mock-search camera --marketplace DE
```

JSON output:

```bash
affiliate-mate-catalog mock-search camera \
  --marketplace DE \
  --format json
```

The mock catalog is deterministic, contains no external calls, and is intentionally small. It is for contract tests and demos, not market research.

## Live Amazon search

After configuring valid Creators API credentials:

```bash
affiliate-mate-catalog amazon-search camera \
  --marketplace DE \
  --search-index All \
  --limit 10
```

Use JSON when feeding catalog discovery into another workflow:

```bash
affiliate-mate-catalog amazon-search camera \
  --marketplace DE \
  --format json
```

The catalog command discovers products only. Affiliate-Mate still requires independent research/evidence before a product becomes a shortlist candidate.

## Why catalog and scoring remain separate

A dangerous architecture would do this:

```text
Amazon says product exists -> guessed commission -> guessed demand -> high score
```

Affiliate-Mate instead requires:

```text
catalog fact
+ explicit commission rule
+ independent market evidence
+ transparent gates
+ sensitivity analysis
= decision
```

That separation makes historical evaluation, provider replacement, auditing, and future market-intelligence adapters possible without rewriting the core decision engine.
