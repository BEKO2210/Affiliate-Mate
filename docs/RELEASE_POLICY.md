# Release Policy

Affiliate-Mate treats releases as reproducible, reviewable transitions between versioned trust boundaries. A release is not created merely because the current branch installs locally.

## Versioning before 1.0

The project follows semantic-versioning intent while APIs are still pre-1.0:

- **minor** (`0.x.0`) — a new milestone/trust boundary or intentionally changed public behavior
- **patch** (`0.x.y`) — correctness/security hardening that does not introduce a new product milestone

Serialized machine contracts carry their own explicit schema versions. A package patch release may still advance a machine-contract version when the serialized shape or safety semantics are incompatible, as v0.7.1 did for backtest reports.

## Mandatory release gates

A release candidate must have all applicable required workflows green on the exact commit being released:

```text
CI
Security
Reproducible Build
```

The expected baseline is:

- Python 3.11 and 3.12 tests pass
- Ruff passes without new blanket suppressions
- source/tests compile
- dependency audit passes
- SPDX SBOM is generated
- package distributions built twice with fixed reproducibility inputs are byte-identical

Additional domain-specific gates remain mandatory: approval integrity, production signoff, leakage-resistant learning tests, and any migration tests affected by the release.

## Release input pinning

The release commit is immutable input. Build jobs should record:

- Git commit SHA
- Affiliate-Mate version
- Python version
- build-tool versions/environment
- `SOURCE_DATE_EPOCH`
- artifact file names
- SHA-256 of every artifact
- SBOM
- signature envelope when release signing is enabled

Do not rebuild an existing version from a different commit and present it as the same artifact.

## Reproducible builds

The repository's reproducibility workflow builds wheel and sdist twice in isolated output directories with a fixed `SOURCE_DATE_EPOCH` and compares their bytes.

A reproducibility failure blocks release until the nondeterministic input is identified. Re-running until two builds happen to match is not an acceptable fix.

## Signatures

v0.8 provides Ed25519 artifact-signing primitives. Release private keys must not be stored in the repository, source configuration, SQLite databases, logs, CI artifacts, or test fixtures.

When signed releases become part of the public release workflow, verification must use a documented trusted public-key fingerprint. A signature from an unknown key proves byte integrity relative to that key, not maintainer identity.

## SBOM and dependency audit

Every release candidate should produce an SPDX SBOM for the build environment and pass the dependency-vulnerability gate.

An SBOM is inventory, not a vulnerability verdict. A clean audit does not replace source review or threat modeling.

## Database compatibility

A release that changes a persistent schema must document:

- source schema version(s)
- destination schema version
- migration transaction boundary
- backup requirement
- rollback/downgrade support or explicit non-support
- immutable-history behavior
- failure/retry semantics

Destructive or lossy migrations require explicit release notes and a validated backup path.

## Release notes

Release notes should contain:

```text
Summary
Trust-boundary changes
Compatibility/schema changes
Security/correctness fixes
Migration steps
Operational changes
Known limitations
Verification/gates
```

Do not describe planned work as shipped capability.

## Stable release criteria

`v1.0.0` is reserved for the point at which the repository has a documented public compatibility policy, supported upgrade path, signed/reproducible release workflow, end-to-end acceptance suite, operational recovery runbook, security/governance documentation, and an independent security/reliability review.
