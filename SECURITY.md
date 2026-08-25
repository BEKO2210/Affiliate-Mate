# Security Policy

Affiliate-Mate handles API credentials, affiliate identifiers, approval lineage, production artifacts, and historical evaluation data. Security issues that can cross those trust boundaries are treated as product defects, not as configuration inconveniences.

## Supported versions

Until 1.0, security fixes are applied to the latest release line. Older pre-1.0 versions may not receive backports.

| Version | Security support |
|---|---|
| latest pre-1.0 | yes |
| older pre-1.0 | best effort / normally upgrade |

## Reporting a vulnerability

Do **not** publish working exploit details, live credentials, private user data, or reproducible secret material in a public issue.

Prefer GitHub's private vulnerability reporting / Security Advisory flow for this repository when it is available. Include:

- affected version or commit
- trust boundary involved
- minimum reproduction
- expected vs. observed behavior
- whether credentials, publishing authority, approval state, or historical evaluation can be bypassed
- any temporary mitigation you verified

If a private reporting channel is temporarily unavailable, open a minimal public issue that says only that a security report needs a private channel. Do not include exploit details there.

## High-priority classes

Examples include:

- credential disclosure in logs, exceptions, artifacts, or generated output
- bypass of research approval or production signoff
- stale approval or stale package authorization becoming valid again
- path traversal or artifact substitution
- live publishing without the explicit feature gate and point-of-use authorization
- idempotency failure causing duplicate external side effects
- signature verification bypass
- backup/restore paths that can replace data without integrity validation
- target/future-data leakage that changes historical evaluation truth
- SQL/data-lineage corruption that silently changes attribution
- dependency compromise affecting the release path

## Secret handling

Secrets must not be committed to the repository or persisted in ordinary SQLite metadata. Provider integrations should depend on the `SecretsProvider` boundary or equivalent process-local secret retrieval.

Normal diagnostics must report secret **presence**, never values. Exception telemetry must not serialize traceback locals or raw exception messages by default.

If a secret is accidentally committed or exposed, treat it as compromised: revoke/rotate it first, then remove it from repository history where appropriate.

## Release and dependency security

The repository's security workflow audits the installed runtime/security dependency set and generates an SPDX SBOM. Release artifacts are intended to be reproducible and content-addressed; v0.8 also provides Ed25519 signing primitives for manifests/artifacts.

A green security workflow is necessary but not proof that the system is vulnerability-free. Review of trust-boundary changes remains mandatory.

## Safe-harbor intent

Good-faith research that avoids privacy violations, destructive actions, service disruption, social engineering, credential theft, and unnecessary data access is welcome. Stop testing and report privately if you encounter real secrets, personal data, or a path to external side effects.
