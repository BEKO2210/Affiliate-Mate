# Affiliate-Mate

**Open-source, evidence-first affiliate research and production planning with auditable approval boundaries.**

Affiliate-Mate is built around one rule:

> **Automation may collect, rank, draft, and plan. It may not silently turn weak evidence into a product claim or turn an old approval into permission to publish.**

The project separates catalog discovery, market intelligence, opportunity scoring, editorial research, approval, and production so no marketplace, data vendor, LLM, renderer, or publisher becomes the trust root.

## What Affiliate-Mate is not

Affiliate-Mate is not a "two prompts = passive income" generator, a storefront scraper, a YouTube HTML scraper, or an auto-publishing spam bot. It makes no income guarantee and does not invent product experience, keyword volume, commission rates, product claims, citations, or human approval.

Most workflows run locally without an LLM or paid cloud account. Live Amazon and YouTube research access remain optional adapters.

## Current status — v0.6 Production Adapters

v0.6 connects the audited v0.5 research package to production planning while preserving a fail-closed trust chain:

- production authorization derived from the effective research approval guard
- authorization bound to an approval event and research SHA-256 digest
- point-of-use stale-approval rechecks
- LLM-neutral structured script interface
- factual script segments linked to approved claim IDs
- credential-free strict template generator for deterministic development
- provider-neutral TTS, video-render, thumbnail, and publisher protocols
- non-side-effecting dry-run adapters
- explicit German and English affiliate-disclosure templates
- deterministic video metadata and thumbnail briefs
- content-addressed artifact manifests
- artifact path and byte-integrity validation
- production package SHA-256 digest
- second human signoff bound to the exact production package
- strict versioned production JSON contracts
- fail-closed publishing dry-run
- fifth CLI: `affiliate-mate-production`

**v0.6 intentionally ships no live publishing adapter.** Passing a publish dry-run means the local preconditions are satisfied; it is not a network side effect.

Previous milestones remain intact:

- **v0.1** — transparent opportunity score
- **v0.2** — evidence store, hard gates, sensitivity, automation JSON
- **v0.3** — Amazon Creators API catalog integration, commission schedules, bounded HTTP
- **v0.4** — YouTube/keyword/trend intelligence, freshness, budgets, replay, clustering
- **v0.5** — claim/evidence ledger, research completeness, approval snapshots, stale-approval protection

## Architecture

```text
Catalogs + market sources
          |
          v
 Evidence Engine
 provenance + time + expiry
          |
          v
 Opportunity Engine
 hard gates + score + sensitivity
          |
          v
      SHORTLIST
          |
          v
 Research Workspace
 sources + claims + citations + notes
          |
          v
 Research completeness
          |
          v
    HUMAN APPROVAL
          |
          v
 Research snapshot SHA-256
          |
          v
 ProductionAuthorization
 approval event + research digest
          |
          v
 Grounded ScriptRequest
 approved claims + source locators
          |
          v
 Structured ScriptDocument
 FACT segment -> claim IDs
          |
          v
 TTS / render / thumbnail plans
          |
          v
 ProductionPackage SHA-256
 metadata + disclosure + asset manifest
          |
          v
 HUMAN PRODUCTION SIGNOFF
          |
          v
    Publish dry-run
          |
          v
 future live publisher
```

A later production stage cannot make an earlier approval valid again. If research changes, the research digest changes and production authorization becomes stale. If the production package changes, its package digest changes and the previous production signoff becomes stale.

## Quick start

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

The package installs five CLIs:

```text
affiliate-mate             evidence + opportunity decision engine
affiliate-mate-catalog     catalog discovery + commission tools
affiliate-mate-intel       market intelligence + replay + clustering
affiliate-mate-research    claims + citations + briefs + human approval
affiliate-mate-production  grounded production planning + publish dry-run
```

## v0.6 production workflow

### 1. Verify production authorization

A raw `APPROVED` value is not enough. This command requires the research package to remain complete and to match the SHA-256 snapshot bound to the latest approval event:

```bash
affiliate-mate-production authorize \
  affiliate-mate.sqlite3 \
  demo-headphones-1
```

The versioned authorization contains:

```text
product_id
approval_event_id
research_digest
created_at
```

### 2. Export an LLM-neutral grounded script request

```bash
affiliate-mate-production script-request \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  --title "Example Headphones" \
  --language de \
  --locale de-DE \
  --output script-request.json
```

The request contains only currently supported claims and their source locators. It explicitly instructs a future generator not to invent first-hand experience, specifications, rankings, prices, guarantees, or comparisons.

### 3. Generate the deterministic baseline script

```bash
affiliate-mate-production script-template \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  --title "Example Headphones" \
  --language de \
  --locale de-DE \
  --output script.json
```

`StrictTemplateScriptGenerator` deliberately reuses approved claim text. It is a safe development baseline, not a polished creative writer.

Every factual segment has explicit claim lineage:

```json
{
  "kind": "fact",
  "text": "The cable is detachable.",
  "claim_ids": ["detachable-cable"]
}
```

A future LLM adapter must return the same structured contract and pass grounding validation before rendering.

### 4. Build the production package

```bash
affiliate-mate-production package \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  script.json \
  --title "Example Headphones" \
  --affiliate-url "https://example.invalid/affiliate" \
  --locale de-DE \
  --output production-package.json
```

The package contains research lineage, script, metadata, disclosure, thumbnail brief, adapter plans, and optional content-addressed artifact records.

For rendered artifacts, the manifest records:

```text
logical name
artifact kind
safe relative path
media type
SHA-256
byte length
```

### 5. Human-sign the exact production package

Research approval and final production review are separate checkpoints:

```bash
affiliate-mate-production signoff \
  production-package.json \
  --actor editor@example \
  --reason "Final script, metadata, disclosure, thumbnail brief, and assets reviewed." \
  --output production-signoff.json
```

The signoff is bound to the exact package SHA-256. Editing the script, metadata, thumbnail instructions, manifest, adapter plans, or research lineage invalidates the old signoff.

### 6. Run the non-side-effecting publish gate

```bash
affiliate-mate-production publish-dry-run \
  affiliate-mate.sqlite3 \
  demo-headphones-1 \
  production-package.json \
  --signoff production-signoff.json \
  --artifact-root ./render-output \
  --output publish-plan.json
```

The strict dry-run checks:

- current approved research snapshot
- production authorization lineage
- structured script grounding
- exact package human signoff
- affiliate disclosure in metadata
- required artifact kinds
- artifact SHA-256 and byte length
- a non-side-effecting publisher plan

For pipeline development before rendered artifacts exist, `--allow-missing-artifacts` skips only artifact presence/integrity. It is not intended as a future live-publish precondition.

## Production contracts

v0.6 defines explicit versioned boundaries:

```text
affiliate-mate.production-authorization.v1
affiliate-mate.script.v1
affiliate-mate.production-package.v1
affiliate-mate.production-signoff.v1
affiliate-mate.publish-plan.v1
```

Deserializers reject unknown versions rather than guessing compatibility.

## Production adapters

Provider-neutral protocols:

```text
ScriptGenerator
TTSAdapter
VideoRenderAdapter
ThumbnailAdapter
PublisherAdapter
```

Bundled v0.6 adapters are deterministic plans only:

```text
strict-template-v1
dry-run-tts-v1
dry-run-video-v1
dry-run-thumbnail-v1
dry-run-youtube-v1
```

They allow the entire production trust chain to be tested without handing an LLM or renderer publishing credentials.

See [`docs/PRODUCTION_ADAPTERS.md`](docs/PRODUCTION_ADAPTERS.md).

## Affiliate disclosures

German and English templates are convenience defaults, not jurisdiction-specific legal advice. The selected description disclosure is required to appear in final metadata. Users remain responsible for affiliate-program terms and applicable disclosure requirements.

## Research approval integrity

v0.5 remains the trust root for product claims. A product is production-ready only when all of these are true:

```text
raw approval == APPROVED
research completeness == PASS
approval snapshot exists
approval snapshot == current research digest
```

See [`docs/APPROVAL_INTEGRITY.md`](docs/APPROVAL_INTEGRITY.md).

## Market intelligence

Affiliate-Mate uses supported APIs or user-owned/licensed exports rather than storefront or YouTube HTML scraping. Market evidence preserves source, timestamp, confidence, expiry, and history. Missing demand or buyer intent is not fabricated.

See [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md).

## Catalog discovery

Affiliate-Mate has a provider-neutral catalog layer, a deterministic mock provider, and an Amazon Creators API adapter. Commission schedules are explicit user data rather than permanent hard-coded percentages.

See [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md).

## Opportunity scoring

The opportunity score remains transparent:

| Component | Weight |
|---|---:|
| Economics / commission per sale | 30% |
| Search demand | 20% |
| Competition opportunity | 20% |
| Buyer intent | 15% |
| Content gap | 10% |
| Evidence quality | 5% |

Estimated affiliate value per 1,000 views is assumption-driven:

```text
1000 × estimated CTR × estimated conversion rate × commission per sale
```

Sensitivity analysis exposes how the result changes under weaker and stronger CTR/conversion assumptions. It is not a revenue promise.

## Product principles

1. **Evidence before generation.** Research first, production later.
2. **Fail closed on critical ambiguity.** Missing evidence is not confidence.
3. **A source is not automatically proof.** Claims need explicit evidence links and review state.
4. **Contradictions are first-class data.** Do not hide them to improve output.
5. **Approval is revision-specific.** A changed research package needs review again.
6. **Production authorization is temporary.** Re-check it at the point of use.
7. **Factual generated content carries claim lineage.**
8. **Research approval and production signoff are separate human checkpoints.**
9. **Artifacts are content-addressed.** Replaced bytes must be detectable.
10. **LLMs and renderers are adapters, not authorities.**
11. **No implicit publishing authority.** Planning and external side effects stay separate.
12. **Original content over mass production.** Repetitive template spam is a non-goal.
13. **Every revenue estimate exposes its assumptions.**

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — trust boundaries and system design
- [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md) — evidence invariants and storage
- [`docs/DECISION_POLICY.md`](docs/DECISION_POLICY.md) — opportunity hard gates
- [`docs/ANALYSIS_OUTPUT.md`](docs/ANALYSIS_OUTPUT.md) — analysis JSON contract
- [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md) — catalog/OAuth contracts
- [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md) — market signals and collectors
- [`docs/RESEARCH_WORKSPACE.md`](docs/RESEARCH_WORKSPACE.md) — claims, citations, reviews, approval
- [`docs/APPROVAL_INTEGRITY.md`](docs/APPROVAL_INTEGRITY.md) — research revision binding
- [`docs/PRODUCTION_ADAPTERS.md`](docs/PRODUCTION_ADAPTERS.md) — v0.6 production trust chain
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — milestones

## Next milestone

**v0.7 — Learning Loop** will import realized channel and affiliate outcomes, compare forecasts with results, calibrate assumptions, detect drift, and backtest scoring changes before they can affect future ranking.

The learning layer must preserve historical versions and avoid target leakage: future conversion data must never rewrite what an earlier point-in-time decision supposedly knew.

## Responsible use

Users are responsible for affiliate disclosures, program terms, API/data licenses, product-claim accuracy, media rights, generated-content review, and platform rules. Affiliate-Mate does not guarantee traffic, conversions, commissions, monetization, or income.

## License

MIT
