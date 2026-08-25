# Recovery Runbook

This runbook defines the minimum safe response when Affiliate-Mate state, artifacts, or an operational job is suspected to be inconsistent.

## 1. Stop side effects

Before diagnosis, disable any external side-effecting adapter. Do not retry publishing, upload, or mutation operations blindly. Preserve the failing workspace and logs.

## 2. Record the incident boundary

Capture:

- Affiliate-Mate version;
- Git commit or release tag when known;
- workspace root and active profile;
- failing command and exit code;
- relevant job/idempotency keys;
- artifact and package digests;
- UTC time of the first observed failure.

Do not copy secrets into the incident record.

## 3. Run diagnostics

From the workspace:

```bash
affiliate-mate status
affiliate-mate doctor --format json
```

For an explicit operational config:

```bash
affiliate-mate-ops doctor --config .affiliate-mate/config.json --format json
```

A failed SQLite integrity or foreign-key check is a hard stop for normal mutation.

## 4. Preserve a backup

Before repair or migration, create a validated backup using the operations CLI. Record the resulting SHA-256 manifest separately from the source database.

Never overwrite the only known-good backup.

## 5. Identify resumable work

Use the operations store's resumable-job view before creating replacement jobs. Reuse the original job/idempotency identity when the operation is the same logical request.

This prevents recovery from becoming a duplicate external side effect.

## 6. Restore when state is corrupt

Restore only from a backup whose SHA-256 matches the expected value. Restore to a new path first when practical. Validate the restored database before replacing active state.

The restore path is atomic, but operational ownership still requires confirming that no other process is writing the destination.

## 7. Revalidate trust lineage

After restore or migration, re-check:

- research approval guard;
- research snapshot freshness;
- production package digest;
- production signoff freshness;
- artifact hashes;
- publish dry-run;
- forecast/package lineage for learning records.

A restored raw approval flag is insufficient if its bound snapshot is stale.

## 8. Resume deliberately

Resume only the smallest failed stage. Do not restart the entire pipeline if a content-addressed, verified prior result is still valid.

For side-effecting adapters, claim or verify idempotency before retrying.

## 9. Escalation conditions

Do not self-repair automatically when any of these are true:

- the source of corruption is unknown;
- a private key or external credential may have been exposed;
- artifact hashes differ after human signoff;
- a migration produced lossy or ambiguous state;
- outcomes appear to have been attributed to the wrong product/content/package;
- a release artifact differs from its published manifest or attestation.

Preserve evidence and require human review.

## Recovery acceptance

Recovery is complete only when diagnostics pass, required lineage checks are current, no duplicate side effect occurred, and the recovered state has a fresh verified backup.
