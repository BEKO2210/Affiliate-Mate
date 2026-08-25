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

- [ ] product brief generation from evidence
- [ ] claim/evidence ledger
- [ ] pros/cons clustering from user-supplied review data
- [ ] citation-ready research notes
- [ ] human approval state machine
- [ ] audit trail for approval decisions
- [ ] research completeness gates
- [ ] source/citation coverage report

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
- silently turning descriptive trend metrics into forecasts
