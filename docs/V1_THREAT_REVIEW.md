# v1 Threat Review

This document is an internal architecture threat review for Affiliate-Mate 1.0. It is **not** an independent third-party security audit or certification.

## Assets

Primary assets include:

- API credentials and affiliate identifiers;
- research sources, claims, approval history, and research snapshots;
- production packages, human signoffs, and rendered artifacts;
- outcome events and immutable forecast history;
- scoring-policy decisions;
- SQLite state and backups;
- release artifacts, SBOMs, manifests, and signing keys.

## Trust boundaries

### External providers → collection adapters

Threats: malicious/malformed responses, stale data, rate-limit behavior, credential leakage, provider schema drift.

Controls: bounded HTTP retries, explicit protocol validation, marketplace/currency checks, point-in-time evidence, credential-free mocks/replay, fail-closed parsing.

### Evidence → decision

Threats: missing evidence treated as truth, stale evidence, opaque ranking, hidden threshold changes.

Controls: required-evidence gates, provenance/timestamps, explicit scoring weights, versioned policies, sensitivity analysis, reject-by-default behavior.

### Research → approval

Threats: unsupported claims, contradictory evidence ignored, stale approval reused after edits.

Controls: claim/evidence links, contradiction gates, source/publisher minimums, append-only claim/approval history, SHA-256 research snapshot bound to approval.

### Approval → production

Threats: model hallucination, ungrounded factual script text, metadata bypass, artifact replacement after review.

Controls: factual segments require claim IDs, authorization is revalidated at point of use, disclosures are part of metadata, package digest binds script/metadata/thumbnail/plans/artifacts, human signoff binds exact package digest, artifact hashes are rechecked.

### Production → publishing

Threats: accidental live upload, duplicate side effects, hidden adapter authority.

Controls: built-in publisher is dry-run, live publishing feature defaults false, side-effecting adapters require explicit certification, operational idempotency claims, publish readiness is not itself execution authority.

### Outcomes → learning

Threats: target leakage, future data in historical evaluation, wrong product/content lineage, double-counted windows, unobservable counterfactuals, automatic policy promotion.

Controls: effective/observed/ingested clocks, immutable forecast snapshots, package/content/product lineage, overlap protection, chronological holdouts, walk-forward evaluation, promotion eligibility separated from human policy decision.

### Workspace → filesystem

Threats: path traversal, accidental writes outside workspace, corrupt/partial writes.

Controls: workspace-relative path validation, escape rejection, atomic text writes, explicit migration planning and backup-before-mutation.

### Release pipeline → consumers

Threats: compromised dependency, nondeterministic rebuild, substituted release artifact, provenance ambiguity, long-lived publishing secret theft.

Controls: dependency audit, SPDX SBOM, reproducible double build, SHA-256 release manifest, GitHub artifact attestations, tag/version match, optional PyPI OIDC Trusted Publishing with no repository PyPI token.

## Residual risks

- External providers can return incorrect factual data that passes syntactic validation.
- A human reviewer can intentionally or accidentally approve weak research.
- A compromised maintainer account can authorize repository changes within its GitHub permissions.
- Third-party plugins can execute arbitrary code once the user explicitly chooses to run them; metadata-only discovery is not a sandbox.
- Platform policy or affiliate-program rules can change independently of this repository.
- No internal test suite proves absence of all vulnerabilities.

## Required response to residual risk

The project avoids claiming that automation establishes truth. Important state changes preserve provenance and human authority, and release/security documentation must state what has actually been tested.

A future independent audit should focus on persistence migrations, plugin execution boundaries, live side-effecting adapters, credential providers, release workflow permissions, and adversarial lineage manipulation.
