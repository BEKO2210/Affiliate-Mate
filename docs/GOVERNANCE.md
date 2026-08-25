# Governance

Affiliate-Mate is maintained as an evidence-first open-source project. Governance exists to protect the trust boundaries, not to maximize feature velocity.

## Decision authority

Maintainers may merge ordinary changes after required CI gates pass. Changes that alter a trust boundary require explicit review of the affected policy, contract, migration, and failure semantics.

Trust-boundary changes include:

- approval semantics;
- publishing authority;
- credential handling;
- persistence and migration semantics;
- serialized machine contracts;
- outcome timing or backtest eligibility;
- release signing, attestations, or package publication;
- plugin execution or sandbox assumptions.

## Human authority invariants

No automated component may grant itself research approval, production signoff, live-publishing authority, or policy-promotion authority.

Automation may calculate eligibility and produce review artifacts. Authority stays with an explicit human action recorded in the relevant domain model.

## Merge standard

A merge candidate must satisfy the repository quality bar and all applicable workflows on the exact head commit. Red gates are evidence, not inconvenience; required checks are fixed in source rather than bypassed by blanket suppressions.

## Security reports

Security issues follow `SECURITY.md`. Do not disclose secrets, exploit details that create unnecessary risk, or user data in public issues.

## Compatibility changes

Stable 1.x compatibility is governed by `docs/COMPATIBILITY_POLICY.md`. Public breakage requires either a compatible migration layer or the next major version.

## Releases

A release is a reviewed transition from one immutable commit to a set of content-addressed artifacts. Tagged release workflows must produce reproducible package artifacts, an SBOM, a SHA-256 manifest, and GitHub provenance attestations.

## External adapters and plugins

Third-party code is not trusted merely because discovery finds it. Metadata discovery and execution are separate boundaries. An adapter that introduces side effects must pass the adapter-certification checklist before being described as production-ready.

## Evidence and claims

Project documentation must distinguish between implemented capability, test evidence, and future plans. Planned work must not be described as shipped. The project must not claim independent audit, external certification, revenue performance, or platform approval without verifiable evidence.
