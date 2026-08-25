# Roadmap

Affiliate-Mate uses milestone releases to harden one trust boundary at a time. Completed milestones remain part of the compatibility surface unless a migration is explicitly documented.

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
- [x] fail-closed required-evidence checks
- [x] sensitivity analysis
- [x] versioned automation JSON
- [x] evidence CLI

## v0.3 — Catalog Integrations

- [x] Amazon Creators API adapter
- [x] adapter contract tests without live credentials
- [x] marketplace-aware currency handling
- [x] explicit commission schedules
- [x] bounded retry/rate-limit handling
- [x] deterministic mock provider
- [x] provider health/error taxonomy
- [x] OAuth token caching + bounded 401 refresh
- [x] catalog CLI
- [x] secrets from environment only

## v0.4 — Market Intelligence

- [x] YouTube Data API competition collector
- [x] user-owned/licensed keyword-demand adapter
- [x] trend + seasonality evidence
- [x] transparent content-gap evidence
- [x] near-duplicate product clustering
- [x] evidence freshness policies
- [x] source-level call budgets
- [x] collection run reports
- [x] deterministic replay mode
- [x] market-intelligence CLI

## v0.5 — Research Workspace

- [x] evidence-backed product briefs
- [x] claim/evidence ledger
- [x] explicit support / contradiction / context stance
- [x] user-supplied review deduplication + clustering
- [x] citation-ready notes
- [x] append-only claim state history
- [x] human approval state machine
- [x] optimistic state-conflict protection
- [x] research completeness gates
- [x] stronger independent evidence for high-risk claims
- [x] contradictory-evidence blocker
- [x] deterministic research snapshot
- [x] approval bound to exact research revision
- [x] stale-approval detection
- [x] effective production-ready guard
- [x] research CLI + versioned brief contract

## v0.6 — Production Adapters

- [x] production entry consumes effective approval guard
- [x] revision-specific production authorization
- [x] point-of-use authorization re-check
- [x] LLM-neutral ScriptGenerator interface
- [x] grounded script requests and factual claim IDs
- [x] deterministic strict-template generator
- [x] script grounding validation
- [x] provider-neutral TTS / video / thumbnail / publisher protocols
- [x] non-side-effecting dry-run adapters
- [x] affiliate disclosure templates
- [x] content-addressed artifact manifest
- [x] artifact path + byte integrity checks
- [x] production package digest
- [x] second human signoff bound to exact package
- [x] stale-signoff detection
- [x] strict versioned production contracts
- [x] fail-closed publishing dry-run
- [x] no live publisher in v0.6
- [x] production CLI + threat-model documentation

## v0.7 — Leakage-Resistant Learning Loop

- [x] provider-neutral realized-outcome event model
- [x] separate effective / observed / ingested timestamps
- [x] immutable source-event identities with idempotent replay
- [x] atomic outcome batch import
- [x] YouTube/video analytics snapshot import
- [x] affiliate click/order/commission/refund/reversal import
- [x] integer minor-unit accounting
- [x] delayed attribution semantics
- [x] explicit product/content/package lineage
- [x] immutable point-in-time forecast snapshots
- [x] frozen candidate + policy + analysis digests
- [x] policy must exist before forecast time
- [x] future-evidence guard during forecast capture
- [x] mature-window predicted-vs-realized performance report
- [x] explicit required-outcome completeness
- [x] CTR / conversion / EV-per-1K calibration
- [x] Wilson 95% intervals for rate metrics
- [x] minimum-sample safeguards
- [x] marketplace/category/price-band cohorts
- [x] calibration drift states
- [x] immutable scoring-policy registry with parent lineage
- [x] baseline historical-decision replay
- [x] replay mismatch promotion blocker
- [x] explicit chronological train/evaluation split
- [x] chronological holdout backtest
- [x] walk-forward fold evaluation
- [x] non-overlapping fold-order guard
- [x] future-data / target-leakage guards
- [x] no automatic policy promotion
- [x] append-only human policy-decision audit
- [x] versioned outcome/forecast/performance/calibration/backtest contracts
- [x] learning-loop CLI
- [x] normative evaluation protocol
- [x] repository-wide engineering quality bar

## v0.8 — Operational Hardening

- [ ] unified typed configuration model
- [ ] configuration schema versions + migrations
- [ ] `affiliate-mate doctor` environment and database diagnostics
- [ ] resumable/idempotent external jobs
- [ ] external-call idempotency keys
- [ ] crash-safe production checkpoints
- [ ] structured event/audit logging
- [ ] OpenTelemetry-compatible observability boundary
- [ ] backup + restore command and automated validation
- [ ] SQLite integrity/foreign-key/lineage diagnostics
- [ ] configurable secrets-provider interface
- [ ] asymmetric signatures for release/production manifests
- [ ] deterministic release builds
- [ ] SBOM generation
- [ ] dependency vulnerability gate
- [ ] branch-protection and release-policy documentation
- [ ] security reporting policy
- [ ] contribution guide
- [ ] changelog/release-note discipline
- [ ] live publisher behind explicit opt-in feature flag
- [ ] live publisher re-checks authorization + signoff immediately before side effects
- [ ] live publisher isolated from model credentials by default

## v0.9 — Product Experience

- [ ] one primary `affiliate-mate` command tree while preserving compatibility shims
- [ ] guided local onboarding wizard
- [ ] workspace/profile model
- [ ] credential-free end-to-end demo workspace
- [ ] shell completion
- [ ] stable machine-readable exit-code contract
- [ ] human-readable diagnostics with remediation hints
- [ ] plugin/adapter registry with capability introspection
- [ ] adapter `doctor` checks
- [ ] explicit stable / beta / dev release channels
- [ ] upgrade + database migration command
- [ ] generated configuration reference
- [ ] documentation site
- [ ] architecture decision records for major trust-boundary choices
- [ ] opt-in diagnostics/telemetry design with privacy documentation
- [ ] reproducible end-to-end acceptance suite

## v1.0 — Stable Open-Source Release

- [ ] freeze public data-contract compatibility policy
- [ ] supported upgrade path from latest pre-1.0 schema
- [ ] signed release artifacts
- [ ] package publishing workflow
- [ ] complete contributor/security/governance documentation
- [ ] end-to-end demo from product discovery through evaluation
- [ ] recovery runbook
- [ ] performance and resource budgets
- [ ] external adapter certification checklist
- [ ] independent security/reliability review
- [ ] release candidate soak period
- [ ] stable release only after all mandatory quality gates pass

## Explicit non-goals

- auto-publishing thousands of interchangeable videos
- bypassing platform restrictions
- scraping where a supported API or user-owned export is the proper boundary
- fake reviews or invented product experience
- guaranteed-income claims
- opaque scoring assumptions
- permanent hard-coded commission truth
- silently turning descriptive trends into forecasts
- unsupported or contradicted claims
- stale approval as production permission
- LLM output as evidence merely because it references a claim ID
- generation models acquiring implicit publishing authority
- future outcomes rewriting historical decisions
- missing reports silently becoming zero outcomes
- learned policy changes bypassing chronological out-of-sample evaluation
- automatic policy promotion without explicit human review
