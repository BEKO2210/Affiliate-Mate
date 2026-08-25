# Compatibility Policy

Affiliate-Mate 1.0 establishes the first stable public compatibility surface.

## Semantic versioning

For the 1.x line:

- patch releases fix defects, security issues, documentation, or operational behavior without intentionally breaking supported inputs;
- minor releases may add commands, fields, adapters, and versioned contracts but must preserve documented 1.x behavior or provide an explicit migration path;
- backwards-incompatible public CLI or serialized-contract changes require a new major version unless the old input remains accepted through a documented compatibility layer.

The installed machine-readable contract is available with:

```bash
affiliate-mate-release contract
```

## Supported Python versions

Affiliate-Mate 1.0 supports Python 3.11 and 3.12. CI must remain green on both before a 1.0.x release is cut.

## CLI compatibility

`affiliate-mate` is the primary CLI. The following executable shims are part of the 1.x compatibility promise:

- `affiliate-mate-catalog`
- `affiliate-mate-intel`
- `affiliate-mate-research`
- `affiliate-mate-production`
- `affiliate-mate-learning`
- `affiliate-mate-ops`

A shim may be deprecated in a future 1.x release only with release notes and a non-breaking replacement path. Removal requires the next major release.

## Machine contracts

Serialized outputs carry explicit schema versions. Consumers must key behavior on those versions rather than assuming that package version and payload shape are identical concepts.

Unknown incompatible schema versions fail closed. Affiliate-Mate must not silently reinterpret an unknown approval, production, forecast, outcome, or evaluation payload.

## Workspace and persistence

Workspace paths remain workspace-relative and escape attempts are rejected. Persistent schema changes must use the documented upgrade mechanism and preserve the pre-mutation backup requirement.

Downgrade is not implicitly guaranteed. If a release cannot safely downgrade a persistent schema, that limitation must be documented before release.

## Safety invariants

The following are compatibility-level safety guarantees in 1.x:

1. research approval is bound to an exact research revision;
2. changed research invalidates stale production authority;
3. production signoff is bound to an exact package digest;
4. artifact tampering blocks publish readiness;
5. built-in live publishing remains fail-closed unless explicitly enabled by a reviewed adapter path;
6. learning evaluation does not grant automatic policy-promotion authority;
7. point-in-time evaluation cannot consume outcomes that were not observable at the evaluation time.

These invariants may become stricter in a 1.x release. They must not be weakened silently.

## Deprecation process

A deprecation must identify:

- the deprecated command, field, or contract;
- the replacement;
- the first version carrying the warning;
- the earliest major version where removal may occur.

Security fixes may reject previously accepted unsafe input without waiting for a major version when preserving that behavior would violate a documented trust boundary.
