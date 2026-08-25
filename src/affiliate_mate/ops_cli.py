"""Operational CLI for diagnostics, recovery, checkpoints, signing, and SBOMs."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .doctor import DoctorReport, run_doctor
from .ops_backup import backup_database, restore_database
from .ops_config import load_config
from .ops_store import OpsStore
from .sbom import sbom_json
from .signing import (
    SignatureEnvelope,
    generate_ed25519_keypair,
    sign_file,
    verify_file,
)


def _time(raw: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be ISO-8601") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return value.astimezone(UTC)


def _load_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path} must contain one JSON object")
    return raw


def _write_json(value: object, output: Path | None = None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")


def _doctor_text(report: DoctorReport) -> str:
    lines = []
    for check in report.checks:
        lines.append(f"[{check.status.value.upper():4}] {check.code}: {check.message}")
        if check.remediation:
            lines.append(f"       remediation: {check.remediation}")
    lines.append(
        f"summary: healthy={str(report.healthy).lower()} "
        f"warnings={report.warning_count} failures={report.failure_count}"
    )
    return "\n".join(lines) + "\n"


def _config_show(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    _write_json(config.to_dict(), args.output)
    return 0


def _doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    report = run_doctor(config)
    if args.format == "json":
        _write_json(report.to_dict(), args.output)
    else:
        text = _doctor_text(report)
        if args.output is None:
            print(text, end="")
        else:
            args.output.write_text(text, encoding="utf-8")
    return report.exit_code


def _backup(args: argparse.Namespace) -> int:
    manifest = backup_database(
        args.source,
        args.destination,
        created_at=args.created_at,
        overwrite=args.overwrite,
    )
    _write_json(manifest.to_dict(), args.manifest)
    return 0


def _restore(args: argparse.Namespace) -> int:
    health = restore_database(
        args.backup,
        args.destination,
        expected_sha256=args.sha256,
        overwrite=args.overwrite,
    )
    _write_json(health.to_dict(), args.output)
    return 0


def _job_begin(args: argparse.Namespace) -> int:
    payload = _load_object(args.payload_json)
    with OpsStore(args.database) as store:
        record, created = store.begin_job(
            job_key=args.job_key,
            kind=args.kind,
            payload=payload,
            at=args.at,
        )
    _write_json({"created": created, "job": record.to_dict()}, args.output)
    return 0


def _job_checkpoint(args: argparse.Namespace) -> int:
    checkpoint = _load_object(args.checkpoint_json)
    with OpsStore(args.database) as store:
        record = store.checkpoint_job(
            args.job_key,
            checkpoint,
            expected_version=args.expected_version,
            at=args.at,
        )
    _write_json(record.to_dict(), args.output)
    return 0


def _job_complete(args: argparse.Namespace) -> int:
    result = _load_object(args.result_json)
    with OpsStore(args.database) as store:
        record = store.complete_job(
            args.job_key,
            result,
            expected_version=args.expected_version,
            at=args.at,
        )
    _write_json(record.to_dict(), args.output)
    return 0


def _job_fail(args: argparse.Namespace) -> int:
    with OpsStore(args.database) as store:
        record = store.fail_job(
            args.job_key,
            args.error,
            expected_version=args.expected_version,
            at=args.at,
        )
    _write_json(record.to_dict(), args.output)
    return 0


def _job_resumable(args: argparse.Namespace) -> int:
    with OpsStore(args.database) as store:
        jobs = store.list_resumable_jobs()
    _write_json({"jobs": [job.to_dict() for job in jobs]}, args.output)
    return 0


def _idempotency_claim(args: argparse.Namespace) -> int:
    request = _load_object(args.request_json)
    with OpsStore(args.database) as store:
        record, created = store.claim_idempotency(
            operation=args.operation,
            key=args.key,
            request=request,
            at=args.at,
        )
    _write_json({"created": created, "claim": record.to_dict()}, args.output)
    return 0


def _idempotency_complete(args: argparse.Namespace) -> int:
    response = _load_object(args.response_json)
    with OpsStore(args.database) as store:
        record = store.complete_idempotency(
            operation=args.operation,
            key=args.key,
            response=response,
            at=args.at,
        )
    _write_json(record.to_dict(), args.output)
    return 0


def _keygen(args: argparse.Namespace) -> int:
    fingerprint = generate_ed25519_keypair(
        args.private_key,
        args.public_key,
        overwrite=args.overwrite,
    )
    _write_json(
        {
            "algorithm": "Ed25519",
            "public_key_fingerprint": fingerprint,
            "private_key": str(args.private_key),
            "public_key": str(args.public_key),
        }
    )
    return 0


def _sign(args: argparse.Namespace) -> int:
    envelope = sign_file(args.file, args.private_key)
    _write_json(envelope.to_dict(), args.output)
    return 0


def _verify(args: argparse.Namespace) -> int:
    envelope = SignatureEnvelope.from_dict(_load_object(args.signature))
    verified = verify_file(args.file, args.public_key, envelope)
    _write_json({"verified": verified, "signature": envelope.to_dict()}, args.output)
    return 0 if verified else 2


def _sbom(args: argparse.Namespace) -> int:
    text = sbom_json(created_at=args.created_at)
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path)


def _add_versioned_job_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("database", type=Path)
    parser.add_argument("job_key")
    parser.add_argument("--expected-version", type=int, required=True)
    parser.add_argument("--at", type=_time, required=True)
    _add_output(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate-ops",
        description=(
            "Diagnose, checkpoint, recover, sign, and inventory Affiliate-Mate operations."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config-show")
    config.add_argument("--config", type=Path)
    _add_output(config)
    config.set_defaults(handler=_config_show)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--config", type=Path)
    doctor.add_argument("--format", choices=("text", "json"), default="text")
    _add_output(doctor)
    doctor.set_defaults(handler=_doctor)

    backup = sub.add_parser("backup")
    backup.add_argument("source", type=Path)
    backup.add_argument("destination", type=Path)
    backup.add_argument("--created-at", type=_time, required=True)
    backup.add_argument("--overwrite", action="store_true")
    backup.add_argument("--manifest", type=Path)
    backup.set_defaults(handler=_backup)

    restore = sub.add_parser("restore")
    restore.add_argument("backup", type=Path)
    restore.add_argument("destination", type=Path)
    restore.add_argument("--sha256", required=True)
    restore.add_argument("--overwrite", action="store_true")
    _add_output(restore)
    restore.set_defaults(handler=_restore)

    begin = sub.add_parser("job-begin")
    begin.add_argument("database", type=Path)
    begin.add_argument("job_key")
    begin.add_argument("kind")
    begin.add_argument("payload_json", type=Path)
    begin.add_argument("--at", type=_time, required=True)
    _add_output(begin)
    begin.set_defaults(handler=_job_begin)

    checkpoint = sub.add_parser("job-checkpoint")
    _add_versioned_job_args(checkpoint)
    checkpoint.add_argument("checkpoint_json", type=Path)
    checkpoint.set_defaults(handler=_job_checkpoint)

    complete = sub.add_parser("job-complete")
    _add_versioned_job_args(complete)
    complete.add_argument("result_json", type=Path)
    complete.set_defaults(handler=_job_complete)

    failed = sub.add_parser("job-fail")
    _add_versioned_job_args(failed)
    failed.add_argument("--error", required=True)
    failed.set_defaults(handler=_job_fail)

    resumable = sub.add_parser("job-resumable")
    resumable.add_argument("database", type=Path)
    _add_output(resumable)
    resumable.set_defaults(handler=_job_resumable)

    claim = sub.add_parser("idempotency-claim")
    claim.add_argument("database", type=Path)
    claim.add_argument("operation")
    claim.add_argument("key")
    claim.add_argument("request_json", type=Path)
    claim.add_argument("--at", type=_time, required=True)
    _add_output(claim)
    claim.set_defaults(handler=_idempotency_claim)

    idem_complete = sub.add_parser("idempotency-complete")
    idem_complete.add_argument("database", type=Path)
    idem_complete.add_argument("operation")
    idem_complete.add_argument("key")
    idem_complete.add_argument("response_json", type=Path)
    idem_complete.add_argument("--at", type=_time, required=True)
    _add_output(idem_complete)
    idem_complete.set_defaults(handler=_idempotency_complete)

    keygen = sub.add_parser("keygen")
    keygen.add_argument("private_key", type=Path)
    keygen.add_argument("public_key", type=Path)
    keygen.add_argument("--overwrite", action="store_true")
    keygen.set_defaults(handler=_keygen)

    sign = sub.add_parser("sign")
    sign.add_argument("file", type=Path)
    sign.add_argument("private_key", type=Path)
    _add_output(sign)
    sign.set_defaults(handler=_sign)

    verify = sub.add_parser("verify")
    verify.add_argument("file", type=Path)
    verify.add_argument("public_key", type=Path)
    verify.add_argument("signature", type=Path)
    _add_output(verify)
    verify.set_defaults(handler=_verify)

    sbom = sub.add_parser("sbom")
    sbom.add_argument("--created-at", type=_time, required=True)
    _add_output(sbom)
    sbom.set_defaults(handler=_sbom)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
