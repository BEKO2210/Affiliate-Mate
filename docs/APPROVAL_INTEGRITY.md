# Approval Integrity

Affiliate-Mate treats **research completeness** and **approval freshness** as two different gates.

A product can have excellent research and still be unapproved. A product can also have a historical `APPROVED` audit event that is no longer usable because the underlying research changed afterward.

Future production adapters must consume the **effective approval guard**, never a raw approval-state value.

## Why a raw approval boolean is insufficient

Consider this sequence:

```text
1. Research package is complete.
2. Human reviewer approves it.
3. A new source is added.
4. A claim is reopened or contradictory evidence is linked.
5. A script generator reads only `approval_state == approved`.
```

Without revision binding, step 5 could generate content from research that the reviewer never approved.

v0.5 closes that gap.

## Snapshot binding

Before a guarded `APPROVED` transition, Affiliate-Mate computes a deterministic SHA-256 digest over the current editorial research package.

The snapshot includes:

- research sources and provenance
- claims
- current claim state
- full claim-state history
- claim/evidence links and their stance
- source locators
- research notes
- note/claim relationships

Approval events themselves are deliberately excluded from the digest. Recording approval therefore does not mutate the package being approved.

The canonical snapshot schema identifier is:

```text
affiliate-mate.research-snapshot.v1
```

The resulting digest is bound to the specific approval audit-event ID in `approval_snapshots`.

A snapshot record is immutable for that event ID. Attempting to bind the same approval event to a different digest raises a research conflict.

## Effective approval guard

`evaluate_approval_guard()` returns production readiness from four independent facts:

```text
raw approval state == APPROVED
        AND
research completeness == PASS
        AND
approval event has a bound snapshot
        AND
bound snapshot digest == current research digest
```

Only when all four conditions are true is:

```text
production_ready = true
```

A raw `APPROVED` row by itself is deliberately insufficient.

## Stale approval

Any mutation represented in the research snapshot changes the digest.

Examples:

- adding a source
- adding a claim
- linking new supporting evidence
- linking contradictory evidence
- adding a note
- changing a claim state
- reopening a claim and later returning it to `supported`

The last example matters: the snapshot contains full claim-state history, so returning to the same visible state does not erase the fact that the research was reopened.

After a mutation:

```text
raw_state       = approved
snapshot_current = false
production_ready = false
```

The package must be reviewed and approved again before production can consume it.

## Fail-closed crash behavior

The guarded approval flow first writes the append-only approval event and then binds the research snapshot.

If snapshot persistence fails after the raw approval event was written, the result is still fail-closed:

```text
raw_state        = approved
snapshot_present = false
production_ready = false
```

Future production code must check the guard, so a partial approval write cannot grant production access.

## Persistence primitive vs guarded service

`ResearchWorkspaceStore.transition_approval()` is a low-level persistence primitive used to append valid state-machine events.

Application code should use:

```python
transition_product_approval(...)
```

for human approval, because that service enforces completeness and snapshot binding.

Even if a caller intentionally bypasses the service and writes a raw `APPROVED` event through the persistence primitive, `evaluate_approval_guard()` rejects it because no valid approval snapshot is present.

This is defense in depth rather than relying on one call site behaving correctly.

## Concurrency model

Approval state transitions already support optimistic `expected_state` checks. If another reviewer changes the approval state first, the stale writer fails instead of silently overwriting the newer state.

The snapshot guard adds a second protection axis: even if research changes around an approval operation, the post-write effective guard re-evaluates completeness and snapshot freshness. If the package no longer matches the approved revision, it remains unusable for production.

## Production contract for v0.6+

A future script, TTS, render, thumbnail, metadata, or publishing adapter must not make its own interpretation of approval.

The intended boundary is:

```text
ResearchWorkspace
      |
      v
evaluate_approval_guard()
      |
      +--- false ---> STOP
      |
      v
approved immutable research revision
      |
      v
production plan / render / publish
```

Production artifacts should also retain the approved research digest in their manifests. That will make it possible to prove exactly which research revision a generated asset came from and to invalidate downstream artifacts when the source research changes.

## Security properties

- approval cannot silently survive research mutation
- raw approval state cannot grant production access by itself
- approval event IDs cannot be rebound to different research digests
- contradictory evidence participates in completeness and the snapshot
- claim-state history cannot be erased by returning to an earlier visible state
- missing snapshot data fails closed
- approval freshness is inspectable in CLI and research-brief output

These properties are intentionally deterministic and do not depend on an LLM.