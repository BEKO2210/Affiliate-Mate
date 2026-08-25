# Stable Release Checklist

A v1 release is eligible for tagging only when every required item below is satisfied on the exact release commit.

## Code and contracts

- [ ] package version and tag match exactly
- [ ] `affiliate-mate-release verify` passes
- [ ] v1 compatibility contract is reviewed
- [ ] no undocumented breaking CLI change
- [ ] no undocumented serialized-schema change
- [ ] migrations and downgrade limitations are documented

## Test and acceptance evidence

- [ ] Python 3.11 CI passes
- [ ] Python 3.12 CI passes
- [ ] Ruff passes
- [ ] source/tests/scripts compile
- [ ] complete pytest suite passes
- [ ] site validation passes
- [ ] credential-free golden v1 acceptance passes within its budget
- [ ] acceptance performs zero live publishing side effects

## Security and supply chain

- [ ] dependency audit passes
- [ ] deterministic SPDX SBOM is generated
- [ ] wheel and normalized sdist are reproducible across isolated double builds
- [ ] built artifacts install successfully
- [ ] release manifest verifies exact SHA-256 and sizes
- [ ] GitHub provenance attestation is generated for release assets
- [ ] no long-lived PyPI credential is present in workflow or repository

## Operations

- [ ] recovery runbook matches current commands
- [ ] backup/restore tests pass
- [ ] workspace upgrade tests pass
- [ ] resumable jobs and idempotency tests pass
- [ ] diagnostics remain secret-safe

## Trust boundaries

- [ ] stale research approval is rejected
- [ ] unsupported/contradicted claims block approval where policy requires
- [ ] factual script segments require approved claim IDs
- [ ] stale production signoff is rejected
- [ ] changed artifacts fail integrity verification
- [ ] side-effecting adapters cannot enter dry-run path silently
- [ ] future/unobservable outcomes cannot enter historical backtests
- [ ] policy promotion still requires explicit human decision

## Documentation

- [ ] changelog describes only shipped capability
- [ ] compatibility policy is current
- [ ] governance is current
- [ ] threat review states residual risk and does not claim independent audit
- [ ] adapter certification requirements are current
- [ ] known limitations are documented

## Release execution

For a tag release:

1. merge the reviewed release commit to `main`;
2. confirm required main-branch workflows are green;
3. create the annotated/signed `vX.Y.Z` tag from that exact commit;
4. allow the `Release` workflow to build, test, manifest, attest, and publish GitHub release assets;
5. enable PyPI Trusted Publishing only after the matching PyPI publisher is configured;
6. verify release assets and provenance from a clean environment.

A partially green release is not a release candidate.
