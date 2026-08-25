# Engineering Quality Bar

Affiliate-Mate is developed as an auditable open-source product, not as a collection of scripts.

This document is the repository-wide acceptance bar for new milestones and integrations. A feature is not considered complete merely because its happy path works.

## 1. Trust boundary first

Every subsystem must state:

- what it is allowed to read,
- what it is allowed to decide,
- what it is allowed to mutate,
- which authority it does **not** possess,
- what happens when required information is missing or stale.

External providers, LLMs, renderers, analytics feeds, and publishers are adapters. None is a trust root.

## 2. Fail closed

Critical ambiguity must produce a visible failure, rejection, or incomplete state.

Forbidden patterns include:

- silently defaulting missing evidence into a passing decision,
- treating a source as proof without an explicit claim link,
- treating model output as evidence,
- treating stale approval as current authorization,
- interpreting missing realized-outcome rows as zero when reporting completeness is unknown,
- using future observations in historical evaluation,
- mutating an active policy as a side effect of a backtest.

## 3. Deterministic contributor path

Every external integration must have a credential-free deterministic path through fixtures, replay data, a mock provider, or a dry-run implementation.

A contributor should be able to exercise the architecture and CI without Amazon, YouTube, an LLM provider, a renderer, or publisher credentials.

## 4. Versioned contracts

Machine-facing artifacts must use explicit schema identifiers.

Unknown schema versions are rejected rather than guessed. Contract changes require a new version or an explicitly documented compatible migration.

Decision-bearing state must retain enough lineage to reproduce what was known at the time.

## 5. Time is part of the data model

For time-dependent evidence or outcomes, timestamps are semantic fields, not logging decoration.

Historical evaluation must distinguish at least:

- when an event happened,
- when a source reported it,
- when Affiliate-Mate learned it.

Backtests and point-in-time resolution may only consume information available at the historical cutoff.

## 6. Integrity and immutability

Where a record represents a historical decision, approval, forecast, artifact, policy, or external event identity:

- exact replay should be idempotent,
- conflicting replay should fail,
- content digests should bind important payloads,
- later mutation should invalidate prior authorization/signoff instead of rewriting history.

Batch imports that can affect evaluation should be atomic.

## 7. Human authority is explicit

Human review is represented as auditable state, not an informal convention.

Research approval, production signoff, and scoring-policy decisions are separate authorities. One must not imply another.

No evaluation result may automatically promote a learned policy.

## 8. Tests target failure modes

A milestone should include tests for the ways it can lie, leak, corrupt, or bypass—not just its happy path.

Examples:

- future evidence in a historical snapshot,
- late-ingested outcomes,
- duplicate source-event identities with changed payloads,
- stale approval after research mutation,
- package mutation after signoff,
- cross-product claim references,
- currency mismatches,
- mixed-currency aggregation,
- insufficient cohort sample sizes,
- baseline replay drift,
- overlapping walk-forward folds.

## 9. Operational behavior is bounded

Retries, API budgets, job concurrency, and external side effects must be explicit and bounded.

Future live publishers must be opt-in and re-check authorization immediately before the side effect.

## 10. Documentation is part of the feature

Each milestone must document:

- purpose,
- threat model / failure model,
- data contracts,
- invariants,
- CLI or API workflow,
- reproducible example,
- non-goals,
- evaluation or verification method.

The README should remain an entry point, not the only specification.

## 11. Release quality

Before a stable release, the repository should provide:

- deterministic build/release workflow,
- supported upgrade and schema-migration policy,
- security reporting policy,
- contribution guide,
- changelog/release notes,
- dependency/SBOM visibility,
- vulnerability checks,
- backup/restore verification,
- branch/release protection guidance,
- first-run diagnostics (`doctor`),
- clear stable/beta/dev release semantics.

## 12. User experience

Power does not excuse friction.

The path to v1.0 should converge toward:

- one primary CLI entry point,
- guided onboarding,
- typed configuration,
- actionable diagnostics,
- shell-friendly JSON output,
- stable exit codes,
- examples that work without credentials,
- migration commands instead of manual database surgery,
- clear recovery instructions.

A high-end developer tool should be strict internally and understandable externally.
