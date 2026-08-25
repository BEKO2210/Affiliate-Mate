# Affiliate-Mate

**Open-source, evidence-first affiliate opportunity research with an audited human approval boundary.**

Affiliate-Mate does not start by generating a video. It starts with a harder question:

> **Which products have enough verifiable economics, demand, market opportunity, and claim-level research to justify publishing anything at all?**

The project is provider-neutral and local-first. Catalog discovery, market intelligence, evidence history, opportunity decisions, editorial research, and future production adapters are deliberately separate layers.

## What Affiliate-Mate is not

Affiliate-Mate is not a "two prompts = passive income" generator, an Amazon scraper, a YouTube scraper, or an auto-publishing spam bot. It makes no income guarantee and does not invent product experience, keyword volume, commission rates, claims, or citations.

Most workflows work without an LLM or cloud account. Live Amazon and YouTube access is optional.

## Current status — v0.5 Research Workspace

v0.5 adds the boundary that should exist before any script, voice, or video generation:

- append-oriented SQLite research workspace
- explicit source provenance records
- claim/evidence ledger
- evidence stance: `supports`, `contradicts`, `context`
- append-only claim state audit history
- optimistic expected-state conflict protection
- citation-ready notes linked to claims
- fail-closed research completeness policy
- stronger independent-source requirements for high-risk claims
- contradictory-evidence approval blocker
- append-only human product approval history
- deterministic user-supplied review deduplication and clustering
- versioned Markdown/JSON product research briefs
- fourth CLI: `affiliate-mate-research`

Previous milestones remain intact:

- **v0.1** — transparent opportunity score
- **v0.2** — evidence store, hard gates, sensitivity, automation JSON
- **v0.3** — Amazon Creators API catalog integration, commission schedules, bounded HTTP
- **v0.4** — YouTube/keyword/trend market intelligence, freshness, budgets, replay, clustering

Affiliate-Mate still performs **no storefront/YouTube HTML scraping, no automatic posting, no LLM content generation, and no invented economics or product claims**.

## Architecture

```text
 Catalog providers                Market evidence providers
 /      |       \                /      |       |       \
mock  Amazon   future         keyword  YouTube  trend   replay
 \      |       /                \      |       |       /
     CatalogItem                  EvidenceObservation
          |                              |
   commission schedule             SQLite evidence history
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
                 Research Workspace
             sources + claims + citations
             notes + review themes + audit
                          |
              fail-closed approval gates
                          |
                    HUMAN APPROVAL
                          |
                future v0.6 production
```

A provider can acquire evidence. It cannot declare a product profitable, mark a product claim true, approve publication, or bypass the decision engine.

## Quick start

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

The package installs four CLIs:

```text
affiliate-mate           evidence + opportunity decision engine
affiliate-mate-catalog   catalog discovery + commission tools
affiliate-mate-intel     market intelligence + replay + clustering
affiliate-mate-research  claims + citations + briefs + human approval
```

## 1. Collect market evidence

A fully credential-free example:

```bash
affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --keyword-csv sample_data/keyword_demand.example.csv \
  --trend-csv sample_data/trend_series.example.csv \
  --replay sample_data/market_replay.example.json \
  --format json
```

The repository fixtures are development data, not current market claims.

Analyze candidates with the persisted evidence:

```bash
affiliate-mate analyze sample_data/products.csv \
  --evidence-db affiliate-mate.sqlite3 \
  --min-evidence-confidence 0.5 \
  --include-rejected
```

## 2. Open a research workspace

The research tables can live in the same SQLite file as market evidence because they use an independent schema namespace:

```bash
affiliate-mate-research init affiliate-mate.sqlite3
```

Add a source:

```bash
affiliate-mate-research source-add affiliate-mate.sqlite3 demo-headphones-1 \
  --source-id manufacturer-spec \
  --kind manufacturer \
  --title "Manufacturer specifications" \
  --locator "https://example.invalid/spec" \
  --publisher "Example Manufacturer"
```

Add a claim. Creating it does **not** make it supported:

```bash
affiliate-mate-research claim-add affiliate-mate.sqlite3 demo-headphones-1 \
  "The cable is detachable." \
  --claim-id detachable-cable \
  --risk medium \
  --actor editor@example
```

Link the claim to a precise source location:

```bash
affiliate-mate-research claim-link affiliate-mate.sqlite3 \
  detachable-cable manufacturer-spec \
  --stance supports \
  --locator "Specifications > Cable" \
  --actor editor@example
```

After a human checks the evidence, append a state transition:

```bash
affiliate-mate-research claim-state affiliate-mate.sqlite3 detachable-cable supported \
  --expected-state draft \
  --actor reviewer@example \
  --reason "Specification checked against the cited source."
```

Add a citation-ready note linked to the claim:

```bash
affiliate-mate-research note-add affiliate-mate.sqlite3 demo-headphones-1 \
  "Cable evidence" \
  "The detachable-cable claim is supported by the manufacturer specification." \
  --claim-id detachable-cable \
  --actor editor@example
```

Inspect the complete audit state:

```bash
affiliate-mate-research status affiliate-mate.sqlite3 demo-headphones-1
```

## 3. Human approval is fail-closed

Start review:

```bash
affiliate-mate-research approval affiliate-mate.sqlite3 demo-headphones-1 in_review \
  --expected-state draft \
  --actor reviewer@example \
  --reason "Research package ready for review."
```

Approval is refused until all configured research gates pass:

```bash
affiliate-mate-research approval affiliate-mate.sqlite3 demo-headphones-1 approved \
  --expected-state in_review \
  --actor reviewer@example \
  --reason "Claims, evidence links, notes, and source diversity verified."
```

Default completeness requires:

| Research gate | Default |
|---|---:|
| sources | >= 2 |
| distinct publishers | >= 2 |
| active claims | >= 1 |
| research notes | >= 1 |
| state of every active claim | `supported` |
| support sources / ordinary claim | >= 1 |
| support sources / high-risk claim | >= 2 |
| distinct publishers / high-risk claim | >= 2 |
| every active claim covered by a note | required |
| contradictory evidence on supported claims | none |

Rejected claims remain in the audit trail but are excluded from active completeness.

## 4. User-supplied review analysis

Affiliate-Mate can triage a user-owned or properly licensed review export without scraping a review site:

```bash
affiliate-mate-research reviews \
  sample_data/reviews.example.csv \
  demo-headphones-1 DE
```

The deterministic baseline:

1. filters product + marketplace strictly,
2. fingerprints normalized text,
3. counts exact duplicate copies,
4. removes duplicate copies before thematic clustering,
5. clusters by explainable token overlap,
6. derives common terms,
7. uses the supplied rating for coarse positive/mixed/negative orientation.

The result is an editorial aid, not a claim that a heuristic cluster represents semantic truth.

## 5. Build a citation-ready product brief

Markdown:

```bash
affiliate-mate-research brief \
  sample_data/products.csv \
  demo-headphones-1 \
  affiliate-mate.sqlite3 \
  --evidence-db affiliate-mate.sqlite3 \
  --reviews-csv sample_data/reviews.example.csv \
  --output research-brief.md
```

Versioned JSON:

```bash
affiliate-mate-research brief \
  sample_data/products.csv \
  demo-headphones-1 \
  affiliate-mate.sqlite3 \
  --format json > research-brief.json
```

The machine-readable contract is:

```text
affiliate-mate.research-brief.v1
```

The brief contains current candidate values, decision gates, sensitivity analysis, evidence resolution, research completeness, claims, evidence links, notes, optional review themes, approval state, and deterministic source references (`S1`, `S2`, ...).

It does not create new product claims.

## Market intelligence

Affiliate-Mate uses the supported YouTube Data API v3 rather than YouTube HTML scraping. Configure live access only through the environment:

```bash
export YOUTUBE_API_KEY="..."

affiliate-mate-intel collect sample_data/products.csv affiliate-mate.sqlite3 \
  --youtube \
  --youtube-language de \
  --youtube-max-results 25 \
  --youtube-max-collections 10
```

Competition and content-gap scores are deterministic heuristics over sampled results and their ingredients are stored in observation metadata. Collection budgets are explicit and bounded.

Keyword demand/buyer intent and trend/seasonality can be supplied through user-owned or licensed exports. Missing values are not fabricated.

See [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md).

## Catalog discovery

Credential-free mock search:

```bash
affiliate-mate-catalog mock-search camera --marketplace DE --format json
```

Live Amazon catalog access targets Amazon Creators API and reads credentials only from environment variables:

```bash
export AMAZON_CREATORS_CREDENTIAL_ID="..."
export AMAZON_CREATORS_CREDENTIAL_SECRET="..."
export AMAZON_CREATORS_CREDENTIAL_VERSION="3.2"
export AMAZON_ASSOCIATE_TAG="..."

affiliate-mate-catalog amazon-search camera --marketplace DE --limit 10
```

Affiliate-Mate does not hard-code permanent Amazon commission rates. Commission schedules are explicit user data.

See [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md).

## Evidence and decision engine

```bash
affiliate-mate score sample_data/products.csv --top 10

affiliate-mate analyze sample_data/products.csv \
  --evidence-db affiliate-mate.sqlite3 \
  --include-rejected \
  --format json
```

The decision automation contract remains:

```text
affiliate-mate.analysis.v1
```

The default opportunity score remains transparent:

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

That is an assumption-driven estimate, not a revenue promise. Sensitivity analysis exposes the effect of weaker/stronger CTR and conversion assumptions.

## Product principles

1. **Evidence before generation.** Research first, content second.
2. **Fail closed on critical ambiguity.** Missing evidence must not become fake confidence.
3. **Provider-neutral core.** Marketplaces and platforms are adapters, not the architecture.
4. **Catalog facts are not market intelligence.** Discovery and judgment remain separate.
5. **A source is not automatically proof.** Claims require explicit evidence links and human state transitions.
6. **Contradictions are first-class data.** Do not hide them to improve a score or brief.
7. **High-risk claims require stronger source diversity.**
8. **Human approval is an auditable state machine, not a boolean shortcut.**
9. **Time and provenance survive normalization.** Market evidence expires.
10. **Prefer supported APIs and user-owned exports over brittle scraping.**
11. **No permanent hard-coded commission truth.**
12. **Retries and external-call budgets are bounded.**
13. **Original content over mass production.** Repetitive template spam is a non-goal.
14. **Every revenue estimate exposes its assumptions.**

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system boundaries
- [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md) — evidence invariants and storage
- [`docs/DECISION_POLICY.md`](docs/DECISION_POLICY.md) — opportunity hard gates
- [`docs/ANALYSIS_OUTPUT.md`](docs/ANALYSIS_OUTPUT.md) — analysis JSON contract
- [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md) — catalog/OAuth contracts
- [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md) — market signals and collectors
- [`docs/RESEARCH_WORKSPACE.md`](docs/RESEARCH_WORKSPACE.md) — v0.5 claims, citations, review analysis, and approval
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestones

## Next milestone

**v0.6 — Production Adapters** can add LLM-neutral script, TTS, render, thumbnail, metadata, and disclosure interfaces. The critical invariant will be: **production may consume only an explicitly approved research package, and live publishing can never bypass that approval boundary.**

## Responsible use

Users are responsible for affiliate disclosures, program terms, API/data licenses, product-claim accuracy, and rights to published media. Affiliate-Mate does not guarantee traffic, conversions, commissions, or income.

## License

MIT
