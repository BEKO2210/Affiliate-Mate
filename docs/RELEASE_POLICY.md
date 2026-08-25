# Release Policy

Affiliate-Mate treats releases as reproducible, reviewable transitions between versioned trust boundaries. A release is not created merely because the current branch installs locally.

## Versioning

Affiliate-Mate follows semantic-versioning intent.

For the stable 1.x line:

- **patch** (`1.0.x`) — correctness, security, documentation, or operational hardening that preserves the documented 1.x compatibility surface
- **minor** (`1.x.0`) — additive capability that preserves documented 1.x behavior or provides a versioned migration path
- **major** (`2.0.0`) — intentionally incompatible public behavior or removal of a supported compatibility path

Serialized machine contracts carry their own explicit schema versions. Package version and serialized schema version are related release inputs, not interchangeable identifiers.

The detailed 1.x promise is in `docs/COMPATIBILITY_POLICY.md` and is available in machine-readable form through `affiliate-mate-release contract`.

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
- source/tests/scripts compile
- site validation passes
- the credential-free golden system acceptance passes within its budget
- dependency audit passes
- SPDX SBOM is generated
- package distributions built twice with fixed reproducibility inputs are byte-identical

Additional domain-specific gates remain mandatory: approval integrity, production signoff, leakage-resistant learning tests, migration tests affected by the release, and stable release-contract verification.

## Release input pinning

The release commit is immutable input. Build jobs record or bind:

- Git commit SHA
- Affiliate-Mate version
- Python version
- build-tool environment
- `SOURCE_DATE_EPOCH`
- artifact file names
- size and SHA-256 of every artifact
- SPDX SBOM
- provenance attestation

Do not rebuild an existing version from a different commit and present it as the same artifact.

## Reproducible builds

The repository's reproducibility workflow builds wheel and sdist twice in isolated output directories with a fixed `SOURCE_DATE_EPOCH` and compares their bytes after deterministic sdist normalization.

A reproducibility failure blocks release until the nondeterministic input is identified. Re-running until two builds happen to match is not an acceptable fix.

## Release manifests and attestations

Tagged releases produce a SHA-256 manifest over package artifacts and the SBOM. The manifest is verified before assets are published.

GitHub artifact attestations establish repository/workflow provenance for release assets. A consumer should still verify the expected repository, tag/commit, manifest, and artifact identity rather than treating the existence of any attestation as universal trust.

## Signatures

Affiliate-Mate also provides Ed25519 artifact-signing primitives. Release private keys must not be stored in the repository, source configuration, SQLite databases, logs, CI artifacts, or test fixtures.

A signature from an unknown key proves integrity relative to that key, not maintainer identity. GitHub provenance attestations and optional maintainer-controlled Ed25519 signatures serve different trust purposes.

## PyPI Trusted Publishing

The release workflow supports PyPI Trusted Publishing through GitHub OIDC and `pypa/gh-action-pypi-publish@release/v1`.

No long-lived PyPI token is required by the workflow. PyPI publication remains disabled unless the repository owner configures the matching Trusted Publisher/environment and explicitly enables the repository variable used by the workflow.

## SBOM and dependency audit

Every release candidate produces an SPDX SBOM and passes the dependency-vulnerability gate.

An SBOM is inventory, not a vulnerability verdict. A clean dependency audit does not replace source review, threat modeling, or provider-specific review.

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

Release notes contain, when applicable:

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

Affiliate-Mate 1.0 requires:

- a documented public compatibility policy;
- a supported workspace upgrade path with pre-mutation backup;
- reproducible package artifacts;
- a content-addressed release manifest;
- provenance-attested tagged release workflow;
- dependency audit and SPDX SBOM;
- end-to-end credential-free acceptance across the principal trust chain;
- operational recovery runbook;
- security, governance, and adapter-certification documentation;
- an internal v1 threat review that records residual risks honestly.

An independent third-party audit is valuable future evidence, but Affiliate-Mate does **not** claim one has occurred unless an external report can be cited. The absence of such an audit must never be disguised by release wording.
