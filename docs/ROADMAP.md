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

- [ ] Amazon Creators API adapter
- [ ] adapter contract tests
- [ ] marketplace-aware currency handling
- [ ] commission schedule import
- [ ] rate-limit and retry handling
- [ ] demo/mock provider for contributors without credentials
- [ ] provider health/error taxonomy

## v0.4 — Market Intelligence

- [ ] YouTube search competition collector
- [ ] keyword-demand adapter
- [ ] trend / seasonality signals
- [ ] SERP/content-gap evidence
- [ ] duplicate / near-duplicate product clustering
- [ ] evidence freshness policies per signal

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
