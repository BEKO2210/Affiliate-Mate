# Adapter Certification

An adapter is not production-ready because it implements a protocol. Side-effecting adapters must satisfy this checklist before Affiliate-Mate documentation may describe them as certified for live use.

## Identity and scope

- adapter name and version are explicit;
- capability is narrow and documented;
- supported marketplaces/platforms are enumerated;
- unsupported operations fail closed.

## Credentials

- credentials are resolved through the designated secret boundary;
- secret values never appear in `repr`, structured diagnostics, telemetry, exceptions, fixtures, or committed configuration;
- least-privilege credentials are documented;
- credential rotation and revocation behavior is documented.

## Inputs and contracts

- all side-effecting inputs use versioned or validated domain objects;
- product/content/package lineage is checked at point of use;
- stale approvals and stale signoffs are rejected;
- unknown schema versions are rejected rather than guessed.

## Idempotency and retries

- an external side effect has a stable idempotency identity;
- retryable and non-retryable failures are distinguished;
- retries are bounded with backoff;
- replay after process crash cannot silently duplicate the operation;
- partial-success semantics are documented.

## Observability

- structured events identify operation, adapter, result class, and correlation identity;
- telemetry does not contain credentials or raw sensitive payloads;
- user-visible errors include remediation without leaking secrets.

## Safety and compliance

- disclosure requirements are preserved through final metadata;
- adapter cannot bypass human research approval or production signoff;
- platform-specific destructive actions require explicit intent;
- test fixtures do not call production endpoints.

## Tests

Certification requires:

- deterministic unit tests;
- protocol/contract fixtures;
- authentication failure tests;
- rate-limit and retry tests;
- idempotent replay tests;
- stale-lineage rejection tests;
- malformed-response tests;
- secret-leak regression tests;
- credential-free dry-run or emulator path;
- at least one manually reviewed sandbox/staging exercise when the provider offers one.

## Certification record

A certification record should contain adapter version, reviewer, date, tested provider/API version, limitations, and evidence links. Certification is invalidated by a material provider API change, authentication model change, or trust-boundary change until re-reviewed.
