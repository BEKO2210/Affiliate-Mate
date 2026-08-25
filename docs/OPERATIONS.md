# Operational Hardening

v0.8 adds an operational control plane around the existing evidence, research, production, and learning layers. Operational state is intentionally **not** business truth: a job checkpoint cannot make a claim supported, approve research, sign a production package, or promote a scoring policy.

## Trust model

```text
Business / research / learning truth
            |
            | immutable IDs + digests
            v
      operational command
            |
     typed configuration
            |
     explicit feature flags
            |
        resumable job
            |
   idempotency claim before
     external side effect
            |
     structured telemetry
            |
            v
       external adapter
```

Recovery, diagnostics, and publishing gates remain separate capabilities.

## Typed configuration

The current configuration contract is:

```text
affiliate-mate.config.v1
```

Example:

```json
{
  "schema_version": "affiliate-mate.config.v1",
  "database": {
    "path": "affiliate-mate.sqlite3"
  },
  "features": {
    "live_publishing": false
  },
  "observability": {
    "jsonl_path": "var/affiliate-mate/ops.jsonl"
  }
}
```

Unknown keys and wrong JSON types fail closed. A string such as `"false"` is **not** accepted where a JSON boolean is required.

Supported environment overrides are deliberately small:

```text
AFFILIATE_MATE_DB
AFFILIATE_MATE_LIVE_PUBLISHING
AFFILIATE_MATE_TELEMETRY_JSONL
```

Environment booleans use an explicit parser; arbitrary non-empty strings are not treated as true.

Legacy `affiliate-mate.config.v0` flat configuration is migrated explicitly to v1. Unknown future schema versions are rejected.

## Doctor

Run:

```bash
affiliate-mate-ops doctor --config affiliate-mate.json
```

or machine-readable:

```bash
affiliate-mate-ops doctor \
  --config affiliate-mate.json \
  --format json \
  --output doctor.json
```

Doctor is side-effect-free. Current checks include:

- supported Python runtime
- configuration schema/digest
- database path
- SQLite `integrity_check`
- SQLite `foreign_key_check`
- discovered Affiliate-Mate schema namespaces/versions
- live-publishing feature-gate visibility
- optional provider secret **presence count only**
- local JSONL telemetry target readiness

Secret values are never returned by doctor.

Warnings do not make the report unhealthy. Failures produce exit code `2`.

## Secrets boundary

`SecretsProvider` separates provider credential lookup from business logic. v0.8 includes:

```text
EnvSecretsProvider
MappingSecretsProvider   # deterministic tests; values hidden from repr
ChainedSecretsProvider
```

The normal configuration file does not contain a generic secret-value bag. Provider adapters should request only the secret names they need at point of use.

## Crash-safe job checkpoints

`OpsStore` owns an independent SQLite namespace:

```text
ops_schema_meta
ops_jobs
ops_idempotency
```

A job starts with a stable `job_key`, kind, and SHA-256 of its input payload. Replaying the same key with identical input is idempotent. Reusing the key with different input is a hard conflict.

Job mutations use optimistic versions:

```text
version 1  begin
version 2  checkpoint
version 3  complete / fail
```

A stale writer cannot overwrite a newer checkpoint.

Example:

```bash
affiliate-mate-ops job-begin ops.sqlite3 render:abc render payload.json \
  --at 2026-01-01T00:00:00+00:00

affiliate-mate-ops job-checkpoint ops.sqlite3 render:abc checkpoint.json \
  --expected-version 1 \
  --at 2026-01-01T00:05:00+00:00

affiliate-mate-ops job-resumable ops.sqlite3
```

## External idempotency

Before a future non-repeatable external side effect, the caller should claim:

```text
operation + idempotency key + request digest
```

Identical replay returns the existing claim. A different request under the same key fails.

After a successful external call, a response digest is bound to the claim. A completed claim cannot later be rebound to a different response.

This store does not magically make an upstream API idempotent. A future adapter should also pass the same idempotency key to providers that support native idempotency.

## Structured telemetry

`TelemetryEvent` uses a versioned JSON boundary:

```text
affiliate-mate.telemetry-event.v1
```

Fields map cleanly to common observability concepts:

```text
name
timestamp
severity
trace_id
span_id
attributes
```

Bundled sinks:

```text
NullTelemetrySink
MemoryTelemetrySink
JsonlTelemetrySink
```

The JSONL sink appends one strict JSON record per line, fsyncs writes, and keeps the file mode at `0600`.

Raw exception messages are **not** emitted automatically because provider errors commonly contain tokens, URLs, file paths, request bodies, or user data. `event_from_exception()` records the exception type and accepts only an explicitly reviewed `safe_message`.

The boundary is OpenTelemetry-compatible in shape, but v0.8 does not require an OpenTelemetry SDK or export data to a remote collector.

## Backup and restore

Create a validated online SQLite backup:

```bash
affiliate-mate-ops backup \
  affiliate-mate.sqlite3 \
  backups/affiliate-mate.sqlite3 \
  --created-at 2026-01-01T00:00:00+00:00 \
  --manifest backups/manifest.json
```

The backup process:

1. uses SQLite's online backup API
2. writes to a temporary file
3. runs `integrity_check`
4. runs `foreign_key_check`
5. atomically moves validated bytes into place
6. records SHA-256, byte length, timestamp, and health in a manifest

Restore requires the expected SHA-256:

```bash
affiliate-mate-ops restore \
  backups/affiliate-mate.sqlite3 \
  restored.sqlite3 \
  --sha256 <expected digest>
```

The backup is checked before copying, the staged restore is checked again, and only then is the destination atomically replaced. Existing destinations require explicit `--overwrite`.

## Ed25519 signing

Install security support:

```bash
python -m pip install -e ".[security]"
```

Generate a key pair:

```bash
affiliate-mate-ops keygen release-private.pem release-public.pem
```

Private key files are forced to mode `0600`. Never commit the private key.

Sign a content-addressed artifact:

```bash
affiliate-mate-ops sign manifest.json release-private.pem --output manifest.sig.json
```

Verify:

```bash
affiliate-mate-ops verify \
  manifest.json \
  release-public.pem \
  manifest.sig.json
```

The signature is over the artifact's SHA-256 bytes. The envelope binds the digest, Ed25519 signature, and public-key fingerprint.

## SBOM

Generate an SPDX 2.3 JSON inventory of the active Python environment:

```bash
affiliate-mate-ops sbom \
  --created-at 2026-01-01T00:00:00+00:00 \
  --output affiliate-mate.spdx.json
```

`created_at` is explicit so release automation can produce deterministic output for a fixed environment.

The SBOM is a package inventory, not a claim that every installed development package is reachable at runtime.

## CI/release gates

v0.8 adds independent workflows for:

```text
CI                  Ruff + compile + full tests on Python 3.11/3.12
Security            dependency audit + SPDX SBOM
Reproducible Build  build twice with fixed SOURCE_DATE_EPOCH and byte-compare
```

A failure must be fixed in code/dependencies/workflow semantics. Required gates should not be bypassed merely to publish a release.

## Live publishing

The operational feature flag defaults to:

```json
{"live_publishing": false}
```

`require_live_publishing_enabled()` is the central operational feature gate available to future side-effecting publishers.

This flag is **necessary but not sufficient**. A future live publisher must still re-check current research authorization, exact production signoff, artifact integrity, and external idempotency immediately before the side effect.

v0.8 still does not add a live publisher.
