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

- [x] unified typed configuration model
- [x] configuration schema versions + migrations
- [x] `affiliate-mate doctor` environment and database diagnostics
- [x] resumable/idempotent external jobs
- [x] external-call idempotency keys
- [x] crash-safe production checkpoints
- [x] structured event/audit logging
- [x] OpenTelemetry-compatible observability boundary
- [x] backup + restore command and automated validation
- [x] SQLite integrity/foreign-key/lineage diagnostics
- [x] configurable secrets-provider interface
- [x] asymmetric signatures for release/production manifests
- [x] deterministic release builds
- [x] SBOM generation
- [x] dependency vulnerability gate
- [x] release-policy documentation
- [x] security reporting policy
- [x] contribution guide
- [x] changelog/release-note discipline
- [x] live publishing behind explicit fail-closed feature policy
- [x] authorization/signoff re-checks at the production boundary
- [x] model credentials separated from publishing authority by design

## v0.9 — Product Experience

- [x] one primary `affiliate-mate` command tree while preserving compatibility shims
- [x] guided local onboarding
- [x] workspace/profile model
- [x] credential-free end-to-end demo workspace
- [x] shell completion
- [x] stable machine-readable exit-code contract
- [x] human-readable diagnostics with remediation hints
- [x] plugin/adapter registry with capability introspection
- [x] adapter `doctor` checks
- [x] explicit stable / beta / dev release channels
- [x] upgrade + database migration command
- [x] generated configuration reference
- [x] project landing page / GitHub Pages workflow
- [x] architecture decision records for major trust-boundary choices
- [x] opt-in diagnostics/telemetry design with privacy documentation
- [x] installed product-facing CLI acceptance coverage

## v1.0 — Stable Open-Source Release

- [x] freeze public 1.x data-contract and CLI compatibility policy
- [x] supported upgrade path from latest pre-1.0 workspace schema
- [x] content-addressed release manifest
- [x] GitHub provenance attestations for tagged release assets
- [x] reproducible wheel and sdist workflow
- [x] optional PyPI Trusted Publishing via GitHub OIDC
- [x] contributor/security/governance documentation
- [x] complete credential-free golden acceptance from discovery through evaluation
- [x] recovery runbook
- [x] performance and resource budgets
- [x] external adapter certification checklist
- [x] internal v1 threat review with residual risks documented
- [x] changelog and stable release checklist
- [ ] stable release only after all mandatory quality gates pass on the exact release head

### Post-1.0 evidence goals

- independent third-party security/reliability assessment
- certified live side-effecting adapters as provider sandboxes and operational evidence permit
- additional Python/runtime support only after CI and compatibility evidence exists

Affiliate-Mate does not claim an independent external audit until an external report can be cited.

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
