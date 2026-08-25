# Affiliate-Mate

**Evidence-first affiliate research, human-approved production, and leakage-resistant learning.**

[![CI](https://github.com/BEKO2210/Affiliate-Mate/actions/workflows/ci.yml/badge.svg)](https://github.com/BEKO2210/Affiliate-Mate/actions/workflows/ci.yml)
[![Security](https://github.com/BEKO2210/Affiliate-Mate/actions/workflows/security.yml/badge.svg)](https://github.com/BEKO2210/Affiliate-Mate/actions/workflows/security.yml)
[![Reproducible Build](https://github.com/BEKO2210/Affiliate-Mate/actions/workflows/reproducible-build.yml/badge.svg)](https://github.com/BEKO2210/Affiliate-Mate/actions/workflows/reproducible-build.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Affiliate-Mate 1.0 is an open-source system for turning product and market signals into auditable affiliate decisions without making a model, marketplace, renderer, publisher, or analytics feed the trust root.

> **Automation may collect, rank, draft, render, and evaluate. It may not fabricate evidence, reuse stale approval, publish by implication, or learn from information that was not observable at the time.**

Project site: **https://beko2210.github.io/Affiliate-Mate/**

## Why Affiliate-Mate exists

Most affiliate automation collapses several very different questions into one pipeline: *is there demand?*, *is a claim supported?*, *should content be produced?*, *is it safe to publish?*, and *did the decision work?*

Affiliate-Mate keeps those boundaries explicit:

```text
Catalog + market signals
          ↓
Evidence + provenance
          ↓
Opportunity gates + sensitivity
          ↓
Research sources + claims + citations
          ↓
HUMAN RESEARCH APPROVAL
          ↓
revision-bound SHA-256 authorization
          ↓
Grounded script + production package
          ↓
HUMAN PRODUCTION SIGNOFF
          ↓
artifact integrity + publish dry-run
          ↓
Immutable forecast
          ↓
Real outcomes with three clocks
          ↓
Calibration / drift / holdout / walk-forward
          ↓
HUMAN POLICY DECISION
```

A valid score is not publication permission. A valid backtest is not policy-promotion permission.

## 1.0 trust guarantees

Affiliate-Mate 1.x freezes these safety invariants as part of the compatibility surface:

- missing required evidence fails closed;
- research approval is bound to an exact research snapshot;
- changed research invalidates stale production authority;
- factual production segments reference approved claim IDs;
- production signoff is bound to an exact package digest;
- changed or missing artifacts block publish readiness;
- built-in publishing remains dry-run/non-side-effecting by default;
- outcome evaluation uses `effective_at`, `observed_at`, and `ingested_at` separately;
- historical evaluation cannot consume outcomes that were not observable by its evaluation time;
- policy promotion remains an explicit human decision;
- unknown incompatible machine-contract versions fail closed.

The machine-readable 1.x promise is available with:

```bash
affiliate-mate-release contract
```

See [`docs/COMPATIBILITY_POLICY.md`](docs/COMPATIBILITY_POLICY.md).

## Quick start

Requirements: **Python 3.11 or 3.12**.

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Create a completely credential-free demo workspace:

```bash
affiliate-mate demo init ./demo
cd demo
affiliate-mate status
affiliate-mate doctor
affiliate-mate analyze data/products.csv --include-rejected
```

No cloud account, API key, live affiliate account, or publishing credential is required for the demo.

## Primary CLI

`affiliate-mate` is the product-facing command tree:

```text
affiliate-mate
├── init
├── workspace
├── demo
├── status
├── doctor
├── plugins
├── upgrade
├── config
├── release
├── completion
├── contract
├── score / analyze / evidence
├── catalog
├── intel
├── research
├── production
├── learning
└── ops
```

Existing domain executables remain supported compatibility shims in 1.x:

```text
affiliate-mate-catalog
affiliate-mate-intel
affiliate-mate-research
affiliate-mate-production
affiliate-mate-learning
affiliate-mate-ops
```

Release verification is exposed separately as `affiliate-mate-release`.

## System layers

### Evidence and decisions

The evidence engine stores provenance, observation time, expiry, confidence, and signal identity in SQLite. Opportunity evaluation uses explicit gates, documented score weights, and CTR/conversion sensitivity rather than a hidden recommendation score.

### Catalog and market intelligence

Provider boundaries include Amazon Creators API catalog access, marketplace-aware currencies, explicit commission schedules, YouTube/keyword/trend evidence, freshness policies, bounded call budgets, deterministic replay, and near-duplicate clustering.

Commission percentages are not treated as permanent hard-coded truth.

### Research workspace

Research is a claim/evidence ledger rather than generated prose pretending to be evidence. It supports source provenance, support/contradiction/context links, claim risk, citation-ready notes, deterministic review clustering, completeness gates, append-only state history, and revision-bound human approval.

### Production

Production consumes only current approved research. Factual script segments carry claim IDs. Packages bind script, metadata, thumbnail guidance, adapter plans, and artifact hashes. A second human signoff binds the exact package digest before the publish dry-run can report readiness.

The built-in publisher path is intentionally non-side-effecting.

### Learning

Forecasts are frozen before outcomes. Realized events retain three clocks:

```text
effective_at  when the outcome happened
observed_at   when the source reported it
ingested_at   when Affiliate-Mate learned it
```

Learning includes mature-window performance reports, refunds/reversals, currency-safe minor-unit accounting, calibration, Wilson intervals, drift states, chronological holdouts, counterfactual-observability guards, and walk-forward evaluation.

A candidate scoring policy can become *promotion eligible*; it cannot promote itself.

### Operations

Operational hardening includes typed versioned configuration, workspace-safe paths, diagnostics, SQLite integrity checks, backup/restore, resumable jobs, idempotency claims, structured secret-safe telemetry, Ed25519 signing primitives, SPDX SBOM generation, dependency auditing, and reproducible distribution builds.

## Golden v1 acceptance

The stable CI runs a credential-free end-to-end acceptance that exercises the principal trust chain as one system:

```text
demo
 → analysis
 → research sources + claim evidence
 → human approval
 → production authorization
 → grounded script
 → five content-addressed artifacts
 → human package signoff
 → non-side-effecting publish dry-run
 → immutable forecast
 → realized views/clicks/orders/commission
 → mature performance report
```

Run it locally:

```bash
python scripts/v1_acceptance.py --max-seconds 20
```

The acceptance path is designed to require **zero network calls, zero credentials, and zero external side effects**.

## Release engineering

A release candidate is not accepted because it merely installs. The repository gates:

```text
CI
  Python 3.11 + 3.12
  Ruff
  compile
  site validation
  full tests
  stable-release verification
  golden acceptance

Security
  dependency vulnerability audit
  deterministic SPDX SBOM

Reproducible Build
  isolated double build
  deterministic sdist normalization
  byte-for-byte comparison
  wheel + sdist install verification
```

Tagged releases additionally support:

- exact tag/version matching;
- SHA-256 release manifest and verification;
- GitHub artifact provenance attestations;
- GitHub Release assets from the verified build;
- optional PyPI Trusted Publishing via GitHub OIDC.

The workflow does not require a long-lived PyPI token. PyPI publication remains externally opt-in until the matching Trusted Publisher/environment is configured.

```bash
affiliate-mate-release verify
affiliate-mate-release performance-budget
```

See [`docs/RELEASE_POLICY.md`](docs/RELEASE_POLICY.md) and [`docs/STABLE_RELEASE_CHECKLIST.md`](docs/STABLE_RELEASE_CHECKLIST.md).

## Machine-readable contracts

Important outputs carry explicit schema versions, including:

```text
affiliate-mate.analysis.v1
affiliate-mate.research-brief.v1
affiliate-mate.production-authorization.v1
affiliate-mate.script.v1
affiliate-mate.production-package.v1
affiliate-mate.production-signoff.v1
affiliate-mate.publish-plan.v1
affiliate-mate.outcome-event.v1
affiliate-mate.forecast-snapshot.v1
affiliate-mate.scoring-policy.v1
affiliate-mate.performance-report.v1
affiliate-mate.calibration-report.v1
affiliate-mate.backtest-report.v2
affiliate-mate.walk-forward-report.v2
affiliate-mate.exit-codes.v1
affiliate-mate.compatibility.v1
affiliate-mate.release-manifest.v1
```

Package and payload versions are deliberately separate concepts.

## Documentation

| Document | Purpose |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | system boundaries and data flow |
| [`docs/COMPATIBILITY_POLICY.md`](docs/COMPATIBILITY_POLICY.md) | stable 1.x compatibility promise |
| [`docs/EVIDENCE_ENGINE.md`](docs/EVIDENCE_ENGINE.md) | evidence storage and time semantics |
| [`docs/CATALOG_INTEGRATIONS.md`](docs/CATALOG_INTEGRATIONS.md) | catalog/OAuth boundary |
| [`docs/MARKET_INTELLIGENCE.md`](docs/MARKET_INTELLIGENCE.md) | market evidence collection |
| [`docs/RESEARCH_WORKSPACE.md`](docs/RESEARCH_WORKSPACE.md) | sources, claims, citations, approval |
| [`docs/APPROVAL_INTEGRITY.md`](docs/APPROVAL_INTEGRITY.md) | revision-bound approval semantics |
| [`docs/PRODUCTION_ADAPTERS.md`](docs/PRODUCTION_ADAPTERS.md) | grounded production and publish safety |
| [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md) | normative learning/evaluation protocol |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | diagnostics, jobs, recovery primitives |
| [`docs/RECOVERY_RUNBOOK.md`](docs/RECOVERY_RUNBOOK.md) | operational incident recovery |
| [`docs/ADAPTER_CERTIFICATION.md`](docs/ADAPTER_CERTIFICATION.md) | live-adapter review requirements |
| [`docs/V1_THREAT_REVIEW.md`](docs/V1_THREAT_REVIEW.md) | internal threat review and residual risk |
| [`docs/GOVERNANCE.md`](docs/GOVERNANCE.md) | maintainer and trust-boundary governance |
| [`docs/RELEASE_POLICY.md`](docs/RELEASE_POLICY.md) | reproducible/attested releases |
| [`docs/QUALITY_BAR.md`](docs/QUALITY_BAR.md) | repository engineering bar |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | completed milestones and post-1.0 evidence goals |

## Security

Report security issues according to [`SECURITY.md`](SECURITY.md). Do not put credentials or sensitive user data into public issues.

`docs/V1_THREAT_REVIEW.md` is an internal review. Affiliate-Mate does **not** claim an independent third-party security audit unless an external report can actually be cited.

## Responsible use

Users remain responsible for affiliate-program terms, disclosures, data/API licenses, claim accuracy, media rights, generated-content review, privacy obligations, and platform rules.

Affiliate-Mate does not guarantee traffic, conversions, commissions, monetization, income, platform approval, or affiliate-program acceptance.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Trust-boundary changes require stronger review than ordinary implementation changes.

## License

MIT — see [`LICENSE`](LICENSE).
