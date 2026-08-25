# Contributing to Affiliate-Mate

Affiliate-Mate is an evidence-first system. Contributions are judged primarily on correctness, reproducibility, and trust-boundary clarity rather than feature count.

## Development setup

```bash
git clone https://github.com/BEKO2210/Affiliate-Mate.git
cd Affiliate-Mate
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Run the same core gates used in CI:

```bash
ruff check .
python -m compileall -q src tests
pytest -q
```

For operational/security work also run:

```bash
affiliate-mate-ops doctor --format json
```

## Pull-request expectations

A focused pull request should explain:

- the failure mode or user need
- the trust boundary affected
- the invariants that must remain true
- the machine contract/schema impact
- migration or compatibility behavior
- adversarial tests added
- what the change intentionally does **not** do

Do not weaken a lint, test, security, integrity, reproducibility, or approval gate merely to make a change pass. Fix the implementation or explain why the gate itself is wrong with a reproducible counterexample.

## Engineering rules

1. **Fail closed for critical ambiguity.** Missing provenance, incompatible currency, stale approval, unknown schema versions, or ambiguous lineage must not become permissive defaults.
2. **Keep acquisition separate from decisions.** A provider adapter may normalize facts; it must not silently decide commercial attractiveness or claim truth.
3. **Preserve point-in-time truth.** Historical evaluation may only use data observable and ingested by the relevant cutoff.
4. **Version machine contracts.** Incompatible serialized output requires a schema/version change and migration notes.
5. **Keep external side effects explicit.** Planning and execution are different operations. Future side-effecting publishers require an explicit feature gate, current authorization, exact package signoff, and idempotency protection.
6. **Do not log secrets.** Tests should prove that normal repr/log/error paths do not disclose credentials.
7. **Prefer deterministic, credential-free tests.** Live APIs do not belong in the required CI path.
8. **Use exact identifiers for lineage.** Do not join product/content/production records by fuzzy title matching.
9. **Keep human authority explicit.** Evaluation eligibility is not approval; research approval is not production signoff; neither implicitly grants live publishing authority.
10. **Document residual risk.** If a boundary is structural rather than semantic, say so.

## Tests

Bug fixes should normally include a regression test that fails before the fix. Trust-boundary work should include adversarial cases such as replay, stale state, conflicting identifiers, future timestamps, partial failures, duplicate delivery, corrupt bytes, unknown schemas, and missing credentials.

Avoid tests that depend on clock time, network availability, random ordering, or live credentials. Inject clocks/sleepers/transports where necessary.

## Database changes

SQLite namespaces are intentionally separated by domain. Any schema change must define:

- current schema version
- upgrade behavior
- downgrade behavior (usually unsupported and explicit)
- transaction boundary
- crash behavior
- idempotency/replay behavior
- backup/restore expectations

Never rewrite an immutable audit/history row as a convenience migration.

## Security-sensitive changes

Review `SECURITY.md` and `docs/QUALITY_BAR.md` before changing authentication, secrets, signing, publishing, approval, backup/restore, outcome attribution, or policy-promotion code.

Do not include real API keys, real affiliate credentials, private reports, or customer/user data in fixtures.

## Style

The project targets Python 3.11+ and uses Ruff. Prefer small typed domain objects, explicit exceptions, dependency injection around external systems, and standard-library primitives unless a dependency materially improves correctness or security.

## Commit/PR scope

Small commits are encouraged when they make review easier, but the final PR must be coherent and CI-green. Generated or mechanical changes should be separated from behavioral changes when possible.

## License

By contributing, you agree that your contribution is made available under the repository's MIT license.
