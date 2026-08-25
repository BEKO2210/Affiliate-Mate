# Research Workspace

v0.5 introduces an editorial research boundary between **opportunity selection** and any future **content generation**.

The goal is not to make an LLM sound confident. The goal is to make every publishable product claim traceable to evidence, reviewable by a human, and impossible to approve while the configured completeness gates fail.

## Core invariants

1. Sources are explicit records with provenance, publisher, retrieval time, and locator.
2. Claims are independent records. Adding a claim does not make it true.
3. Claim state changes are append-only audit events.
4. Evidence links have an explicit stance: `supports`, `contradicts`, or `context`.
5. A claim and source from different products cannot be linked.
6. Notes can reference only claims for the same product.
7. Product approval is an append-only state machine.
8. `APPROVED` is fail-closed behind research completeness gates.
9. High-risk claims require stronger and more diverse evidence than ordinary claims.
10. User-supplied review analysis is deterministic and never presented as semantic ground truth.
11. The research brief does not invent claim text; it renders recorded claims and their evidence.
12. No approval state grants permission to auto-publish. Publishing remains a future, separate boundary.

## Storage model

`ResearchWorkspaceStore` uses SQLite and can share a file with the Evidence Engine because it owns a separate schema namespace and version marker (`research_schema_meta`).

The primary tables are:

```text
research_sources
research_claims
claim_state_events
claim_evidence_links
research_notes
note_claim_links
approval_events
```

State history is append-only. The current state is the latest event, not a mutable status column.

## Claim workflow

```text
DRAFT
  |\
  | +------> DISPUTED
  |             |
  v             v
SUPPORTED <-----+
  |             |
  +----------> REJECTED
                 |
                 v
               DRAFT
```

A rejected claim must return to draft before it can become supported again. This avoids an unaudited `rejected -> supported` shortcut.

Optimistic transitions can include an expected state. If another process or reviewer changed the state first, the transition fails with a conflict rather than silently overwriting the new decision.

## Product approval workflow

```text
DRAFT -> IN_REVIEW -> APPROVED
          |   ^           |
          |   |           |
          v   |           v
       REJECTED          IN_REVIEW
          |
          +-----> DRAFT
```

An approved product can be reopened when new evidence appears.

`APPROVED` is special: the policy is evaluated immediately before the state event is appended. If any required gate fails, no approval event is written.

## Default completeness policy

The defaults are deliberately conservative starting points, not universal truths:

| Gate | Default |
|---|---:|
| research sources | >= 2 |
| distinct publishers | >= 2 |
| active claims | >= 1 |
| research notes | >= 1 |
| ordinary claim support sources | >= 1 |
| high-risk claim support sources | >= 2 |
| high-risk distinct publishers | >= 2 |
| active claim state | `supported` |
| active claim note coverage | required |
| contradictory evidence on supported claims | none |

Rejected claims are retained for audit but excluded from active completeness.

## Source records

A source contains:

- `source_id`
- `product_id`
- source kind
- title
- locator (URL, file reference, document identifier, etc.)
- publisher
- retrieval timestamp
- optional publication timestamp
- optional checksum
- optional structured metadata

A source record is provenance, not proof by itself. The relationship between a source and a claim is represented explicitly by a claim-evidence link.

## Claim-evidence links

Each link records:

- claim ID
- source ID
- stance (`supports`, `contradicts`, `context`)
- a page/section/timestamp/record locator
- optional short quote or evidence note
- actor
- creation time

The same source can support one claim and provide context for another. Contradictions are first-class data rather than something the system hides to improve a score.

## Citation-ready notes

Notes are product-scoped records that can link to one or more claims. The default approval policy requires every active claim to appear in a note, which prevents an approved workspace from containing evidence-backed claims that never made it into the editorial research record.

## Review corpus analysis

`review_analysis.py` accepts user-owned or properly licensed CSV exports. It does not scrape review websites.

Required columns:

```csv
review_id,product_id,marketplace,rating,body,source
```

Optional:

```csv
title
```

The deterministic baseline:

1. filters strictly by product and marketplace,
2. fingerprints normalized text to count exact duplicates,
3. removes exact duplicate copies before thematic clustering,
4. computes explainable token-overlap similarity,
5. clusters reviews with transitive union-find grouping,
6. labels each cluster with common terms,
7. derives coarse positive/mixed/negative orientation from the supplied rating, not from invented text sentiment.

This is intentionally transparent. It is useful for triage and editorial discovery, but it is not a claim that the cluster represents the true meaning of every review.

Example:

```bash
affiliate-mate-research reviews \
  sample_data/reviews.example.csv \
  demo-headphones-1 DE
```

## CLI workflow

Initialize a workspace:

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

Add a claim:

```bash
affiliate-mate-research claim-add affiliate-mate.sqlite3 demo-headphones-1 \
  "The cable is detachable." \
  --claim-id detachable-cable \
  --risk medium \
  --actor editor@example
```

Link evidence:

```bash
affiliate-mate-research claim-link affiliate-mate.sqlite3 \
  detachable-cable manufacturer-spec \
  --stance supports \
  --locator "Specifications > Cable" \
  --actor editor@example
```

Move the claim to supported after human review:

```bash
affiliate-mate-research claim-state affiliate-mate.sqlite3 detachable-cable supported \
  --expected-state draft \
  --actor reviewer@example \
  --reason "Specification checked against source."
```

Add a note:

```bash
affiliate-mate-research note-add affiliate-mate.sqlite3 demo-headphones-1 \
  "Cable evidence" \
  "The detachable-cable claim is supported by the manufacturer specification." \
  --claim-id detachable-cable \
  --actor editor@example
```

Inspect completeness and audit state:

```bash
affiliate-mate-research status affiliate-mate.sqlite3 demo-headphones-1
```

Start human review:

```bash
affiliate-mate-research approval affiliate-mate.sqlite3 demo-headphones-1 in_review \
  --expected-state draft \
  --actor reviewer@example \
  --reason "Research package ready for review."
```

Approve only after the gates pass:

```bash
affiliate-mate-research approval affiliate-mate.sqlite3 demo-headphones-1 approved \
  --expected-state in_review \
  --actor reviewer@example \
  --reason "Claims, citations, and notes verified."
```

If completeness fails, the command exits non-zero and prints the failed research report. No approval event is appended.

## Research briefs

The brief combines:

- current normalized candidate values,
- opportunity decision and sensitivity analysis,
- optional persisted market-evidence resolution,
- research completeness,
- claims and claim states,
- evidence links,
- citation-ready notes,
- optional review themes,
- approval state,
- deterministic source references (`S1`, `S2`, ...).

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

The JSON schema identifier is:

```text
affiliate-mate.research-brief.v1
```

## What v0.5 still refuses to do

- invent product claims
- infer that a claim is supported merely because a source exists
- hide contradictory evidence
- scrape user-review sites as a default data source
- treat review clusters as factual product claims
- approve incomplete research
- auto-generate fake first-hand experience
- auto-publish content

Those constraints are deliberate. v0.6 can add production adapters without weakening the research boundary established here.
