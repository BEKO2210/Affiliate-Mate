# Roadmap

## v0.1 — Foundation

- [x] normalized product model
- [x] transparent opportunity score
- [x] commission and EV/1K calculations
- [x] CSV input
- [x] CLI ranking
- [x] tests and CI

## v0.2 — Evidence Engine

- [x] source/provider protocols
- [x] SQLite evidence store
- [x] provenance + observation timestamps
- [x] expiry-aware point-in-time lookup
- [x] persisted-evidence candidate resolution
- [x] hard rejection gates
- [x] fail-closed required-evidence checks for analysis
- [x] sensitivity analysis for CTR/conversion assumptions
- [x] score explanations and rejection reasons
- [x] versioned JSON output for automation
- [x] evidence CLI (`init`, `add`, `latest`)

## v0.3 — Catalog Integrations

- [x] Amazon Creators API adapter
- [x] adapter contract tests with no live credentials required
- [x] marketplace-aware currency handling
- [x] explicit commission schedule import
- [x] bounded rate-limit and retry handling
- [x] demo/mock provider for contributors without credentials
- [x] provider health/error taxonomy
- [x] OAuth token caching + bounded 401 refresh
- [x] separate catalog-discovery CLI
- [x] live-provider secrets only through environment variables

## v0.4 — Market Intelligence

- [x] YouTube Data API competition collector
- [x] user-owned/licensed keyword-demand adapter
- [x] trend + seasonality signals from explicit time-series exports
- [x] transparent YouTube content-gap evidence
- [x] duplicate / near-duplicate product clustering
- [x] evidence freshness policies per signal
- [x] source-level call budgets
- [x] provider collection run reports
- [x] deterministic fixture/replay mode for external evidence
- [x] separate market-intelligence CLI
- [x] credential-free examples for keyword, trend, and replay workflows

A generic web-SERP scraper is deliberately not part of v0.4. Supported APIs or user-owned exports remain the preferred boundary.

## v0.5 — Research Workspace

- [x] product brief generation from evidence
- [x] claim/evidence ledger with explicit evidence stance
- [x] deterministic clustering from user-supplied review data
- [x] exact duplicate review detection before clustering
- [x] citation-ready research notes
- [x] append-only claim state history
- [x] human approval state machine
- [x] append-only approval audit trail
- [x] optimistic expected-state conflict detection
- [x] research completeness gates
- [x] stronger independent-support gates for high-risk claims
- [x] contradictory-evidence approval blocker
- [x] source/citation coverage report
- [x] deterministic SHA-256 research snapshot
- [x] approval-event binding to an immutable research revision
- [x] stale-approval detection after any research mutation
- [x] effective `production_ready` approval guard
- [x] versioned research brief JSON contract
- [x] dedicated `affiliate-mate-research` CLI

## v0.6 — Production Adapters

- [x] production entry gate consumes effective approval guard, never raw approval state
- [x] production authorization bound to approval event + research SHA-256 digest
- [x] point-of-use production authorization re-check
- [x] LLM-neutral `ScriptGenerator` interface
- [x] grounded `ScriptRequest` exports approved claims and source locators only
- [x] structured factual script segments carry claim IDs
- [x] deterministic credential-free strict-template generator
- [x] script-grounding validation against current supported research claims
- [x] `TTSAdapter` interface
- [x] `VideoRenderAdapter` interface
- [x] `ThumbnailAdapter` interface
- [x] `PublisherAdapter` interface
- [x] deterministic non-side-effecting TTS/render/thumbnail/publish plans
- [x] thumbnail brief generator with claim-safe default guidance
- [x] YouTube-oriented metadata generator
- [x] German + English affiliate disclosure templates
- [x] disclosure-presence package invariant
- [x] content-addressed artifact manifest
- [x] safe relative artifact-path validation
- [x] artifact SHA-256 + byte-length integrity validation
- [x] production package retains approval event + approved research digest
- [x] deterministic production package SHA-256
- [x] second human signoff bound to exact production package digest
- [x] package mutation / stale-signoff detection
- [x] versioned production authorization/script/package/signoff/publish-plan contracts
- [x] strict production JSON deserialization
- [x] fail-closed publishing dry-run
- [x] strict dry-run rejects side-effecting publisher plans
- [x] no live publisher included in v0.6
- [x] dedicated `affiliate-mate-production` CLI
- [x] production trust-boundary and threat-model documentation

## v0.7 — Learning Loop

- [ ] provider-neutral realized-outcome event model
- [ ] import YouTube/video analytics snapshots
- [ ] import affiliate click/conversion/revenue reports
- [ ] normalize refunds, reversals, and delayed attribution
- [ ] preserve observation time, ingestion time, source, and reporting window
- [ ] join outcomes to product/video/production-package lineage without lossy title matching
- [ ] predicted-vs-realized performance report
- [ ] CTR calibration by marketplace/category/price band
- [ ] conversion-rate calibration by marketplace/category/price band
- [ ] commission/revenue realization calibration
- [ ] confidence intervals and minimum-sample safeguards
- [ ] calibration drift detection
- [ ] cohort stability report
- [ ] scoring-policy version registry
- [ ] backtest candidate scoring changes before adoption
- [ ] walk-forward evaluation for scoring-policy changes
- [ ] explicit train/evaluation time split
- [ ] target-leakage / future-data guards
- [ ] historical replays retain the policy version known at decision time
- [ ] no automatic model/policy promotion without evaluation gates
- [ ] learning-loop CLI and versioned machine-readable reports

## v0.8 — Operational Hardening

- [ ] asymmetric signatures for release/production manifests
- [ ] configurable secrets-provider interface
- [ ] resumable/idempotent external jobs
- [ ] external-call idempotency keys
- [ ] crash-safe production checkpoints
- [ ] structured event/audit logging
- [ ] OpenTelemetry-compatible observability boundary
- [ ] backup/restore validation for evidence and research stores
- [ ] deterministic release builds
- [ ] SBOM generation
- [ ] dependency vulnerability gate
- [ ] branch protection / release policy documentation
- [ ] future live publisher behind an explicit opt-in feature flag
- [ ] live publisher re-checks production authorization and package signoff immediately before side effects
- [ ] live publisher never receives LLM/model credentials by default

## Explicit non-goals

- auto-publishing thousands of interchangeable videos
- bypassing platform restrictions
- scraping where a supported API or user export is the proper interface
- fake reviews or invented product experience
- guaranteed-income claims
- hiding score assumptions behind an opaque model
- hard-coding affiliate commission rates as permanent truth
- silently turning descriptive trend metrics into forecasts
- approving unsupported or contradicted claims
- treating a stale historical approval as permission for production
- treating LLM output as evidence merely because it cites a claim ID
- letting a generation model implicitly acquire publishing authority
- rewriting historical decisions with future outcome data
- silently promoting a learned scoring change without out-of-sample evaluation
