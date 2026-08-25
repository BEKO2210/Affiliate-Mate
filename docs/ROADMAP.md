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

- [ ] YouTube search competition collector
- [ ] keyword-demand adapter
- [ ] trend / seasonality signals
- [ ] SERP/content-gap evidence
- [ ] duplicate / near-duplicate product clustering
- [ ] evidence freshness policies per signal
- [ ] source-level rate-limit budgets and collection run reports
- [ ] deterministic fixture/replay mode for external providers

## v0.5 — Research Workspace

- [ ] product brief generation from evidence
- [ ] claim/evidence ledger
- [ ] pros/cons clustering from user-supplied review data
- [ ] citation-ready research notes
- [ ] human approval state machine
- [ ] audit trail for approval decisions

## v0.6 — Production Adapters

- [ ] LLM-neutral script interface
- [ ] TTS adapter interface
- [ ] video-render adapter interface
- [ ] thumbnail brief generator
- [ ] YouTube metadata generator
- [ ] affiliate disclosure templates
- [ ] no-publish-without-approval invariant

## v0.7 — Learning Loop

- [ ] import video analytics
- [ ] import affiliate conversion reports
- [ ] calibrate CTR and conversion assumptions
- [ ] compare predicted vs realized performance
- [ ] backtest scoring changes before adoption
- [ ] calibration drift report

## Explicit non-goals

- auto-publishing thousands of interchangeable videos
- bypassing platform restrictions
- scraping where an official API or user export is the proper interface
- fake reviews or invented product experience
- guaranteed-income claims
- hiding score assumptions behind an opaque model
- hard-coding affiliate commission rates as permanent truth
