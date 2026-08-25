# Changelog

All notable stable changes to Affiliate-Mate are recorded here.

## 1.0.0 — 2026-08-25

Affiliate-Mate 1.0 freezes the first stable compatibility surface for an evidence-first affiliate research and production system.

### Product surface

- unified `affiliate-mate` CLI with portable workspaces, onboarding, status, diagnostics, plugins, upgrades, config reference, release channels, and shell completion
- compatibility shims retained for catalog, intelligence, research, production, learning, and operations CLIs
- deterministic credential-free demo path
- public v1 compatibility and performance-budget contracts

### Trust chain

- evidence provenance and point-in-time resolution
- fail-closed opportunity gates and explicit sensitivity analysis
- claim/evidence ledger with contradiction handling and citation-ready notes
- revision-bound human research approval
- claim-grounded production scripts and content-addressed artifacts
- package-bound human production signoff and non-side-effecting publish dry-run
- immutable forecasts, three-clock outcomes, delayed attribution, calibration, drift detection, chronological holdouts, and walk-forward evaluation
- human-only scoring-policy promotion decisions

### Operations and supply chain

- workspace-safe paths and explicit schema upgrades with backup before mutation
- SQLite integrity diagnostics, validated backup/restore, resumable jobs, and idempotency claims
- secret-safe diagnostics and structured telemetry boundaries
- Ed25519 signing primitives
- dependency vulnerability audit and deterministic SPDX 2.3 SBOM generation
- reproducible wheel/sdist gate
- SHA-256 release manifests
- GitHub artifact attestations for tagged release assets
- optional PyPI Trusted Publishing through GitHub OIDC; no long-lived PyPI token is required by the workflow

### Stable acceptance

The v1 release gate includes a credential-free golden acceptance that traverses:

`demo → analysis → research → human approval → production → human signoff → publish dry-run → forecast → outcomes → performance evaluation`

The acceptance path performs no live publishing and no external network calls.

### Compatibility

See `docs/COMPATIBILITY_POLICY.md`. Serialized contracts retain explicit schema versions and unknown incompatible schema versions fail closed.

### Known limitations

- Affiliate-Mate does not guarantee income or affiliate-program acceptance.
- Built-in production adapters remain dry-run oriented unless an explicitly reviewed side-effecting adapter is introduced later.
- External plugin metadata can be discovered without executing plugin code, but third-party plugin behavior is not trusted by default.
- PyPI publication requires the repository owner to configure the matching PyPI Trusted Publisher and enable the repository variable described in the release documentation.
