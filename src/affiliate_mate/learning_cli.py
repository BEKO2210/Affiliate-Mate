"""CLI for immutable outcome ingestion, calibration, and leakage-resistant backtests."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .analysis import analyze_candidate
from .decision import EvaluationPolicy
from .evidence import SQLiteEvidenceStore
from .io import load_candidate_inputs_csv
from .learning_backtest import (
    BacktestPolicy,
    PolicyFold,
    backtest_policy_change,
    walk_forward_backtest,
)
from .learning_capture import capture_forecast, evaluation_policy_from_version
from .learning_importers import load_affiliate_outcomes_csv, load_video_analytics_csv
from .learning_models import ScoringPolicyVersion
from .learning_reports import (
    CalibrationPolicy,
    PerformancePolicy,
    build_calibration_report,
    build_performance_report,
)
from .learning_store import LearningStore


def _time(raw: str) -> datetime:
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None or value.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return value.astimezone(UTC)


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain one JSON object")
    return value


def _write_json(value: object, output: Path | None = None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.write_text(text, encoding="utf-8")


def _init(args: argparse.Namespace) -> int:
    with LearningStore(args.database) as store:
        store.initialize()
    _write_json({"status": "ok", "database": str(args.database)})
    return 0


def _policy_register(args: argparse.Namespace) -> int:
    payload = (
        EvaluationPolicy().to_dict()
        if args.policy_json is None
        else _load_json_object(args.policy_json)
    )
    entry = ScoringPolicyVersion(
        version=args.version,
        policy_payload=payload,
        created_at=args.created_at,
        parent_version=args.parent_version,
        notes=args.notes,
    )
    with LearningStore(args.database) as store:
        inserted = store.register_policy(entry)
    _write_json({"inserted": inserted, "policy": entry.to_dict()})
    return 0


def _forecast(args: argparse.Namespace) -> int:
    candidates = load_candidate_inputs_csv(args.products_csv)
    matches = [item for item in candidates if item.candidate.product_id == args.product_id]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one product_id {args.product_id!r}, found {len(matches)}"
        )
    item = matches[0]
    with LearningStore(args.database) as store:
        policy_version = store.get_policy(args.policy_version)
        if policy_version is None:
            raise KeyError(f"unknown policy_version: {args.policy_version}")
        evaluation_policy = evaluation_policy_from_version(policy_version)
        if args.evidence_db is None:
            result = analyze_candidate(
                item.candidate,
                policy=evaluation_policy,
                provided_fields=item.provided_fields,
            )
        else:
            with SQLiteEvidenceStore(args.evidence_db) as evidence_store:
                result = analyze_candidate(
                    item.candidate,
                    policy=evaluation_policy,
                    provided_fields=item.provided_fields,
                    evidence_store=evidence_store,
                    as_of=args.predicted_at,
                    min_evidence_confidence=args.min_evidence_confidence,
                )
        forecast = capture_forecast(
            result,
            predicted_at=args.predicted_at,
            horizon_days=args.horizon_days,
            content_id=args.content_id,
            category=args.category,
            policy_version=policy_version,
            evaluation_policy=evaluation_policy,
            package_digest=args.package_digest,
        )
        inserted = store.add_forecast(forecast)
    _write_json({"inserted": inserted, "forecast": forecast.to_dict()}, args.output)
    return 0


def _import_video(args: argparse.Namespace) -> int:
    events = load_video_analytics_csv(
        args.csv,
        ingested_at=args.ingested_at,
        source=args.source,
    )
    with LearningStore(args.database) as store:
        inserted, replayed = store.add_outcomes(events)
    _write_json({"events": len(events), "inserted": inserted, "replayed": replayed})
    return 0


def _import_affiliate(args: argparse.Namespace) -> int:
    events = load_affiliate_outcomes_csv(
        args.csv,
        ingested_at=args.ingested_at,
        source=args.source,
    )
    with LearningStore(args.database) as store:
        inserted, replayed = store.add_outcomes(events)
    _write_json({"events": len(events), "inserted": inserted, "replayed": replayed})
    return 0


def _performance_policy(args: argparse.Namespace) -> PerformancePolicy:
    return PerformancePolicy(reporting_lag_days=args.reporting_lag_days)


def _performance(args: argparse.Namespace) -> int:
    with LearningStore(args.database) as store:
        forecast = store.get_forecast(args.forecast_id)
        if forecast is None:
            raise KeyError(f"unknown forecast_id: {args.forecast_id}")
        report = build_performance_report(
            store,
            forecast,
            evaluated_at=args.evaluated_at,
            policy=_performance_policy(args),
        )
    _write_json(report.to_dict(), args.output)
    return 0 if report.sample_eligible else 2


def _calibrate(args: argparse.Namespace) -> int:
    with LearningStore(args.database) as store:
        forecasts = store.list_forecasts(
            start=args.start,
            end=args.end,
            marketplace=args.marketplace,
        )
        perf_policy = _performance_policy(args)
        reports = [
            build_performance_report(
                store,
                forecast,
                evaluated_at=args.evaluated_at,
                policy=perf_policy,
            )
            for forecast in forecasts
        ]
    report = build_calibration_report(
        reports,
        evaluated_at=args.evaluated_at,
        policy=CalibrationPolicy(
            min_forecasts=args.min_forecasts,
            min_views=args.min_views,
            min_clicks=args.min_clicks,
            min_orders=args.min_orders,
            relative_drift_threshold=args.relative_drift_threshold,
        ),
    )
    _write_json(report.to_dict(), args.output)
    return 0


def _backtest_policy(args: argparse.Namespace) -> BacktestPolicy:
    return BacktestPolicy(
        min_evaluation_forecasts=args.min_evaluation_forecasts,
        min_candidate_selections=args.min_candidate_selections,
        max_relative_ev_regression=args.max_relative_ev_regression,
        performance_policy=_performance_policy(args),
    )


def _backtest(args: argparse.Namespace) -> int:
    with LearningStore(args.database) as store:
        report = backtest_policy_change(
            store,
            baseline_version=args.baseline_version,
            candidate_version=args.candidate_version,
            marketplace=args.marketplace,
            train_cutoff=args.train_cutoff,
            evaluation_end=args.evaluation_end,
            evaluated_at=args.evaluated_at,
            policy=_backtest_policy(args),
        )
    _write_json(report.to_dict(), args.output)
    return 0 if report.promotion_eligible else 2


def _walk_forward(args: argparse.Namespace) -> int:
    raw = json.loads(args.folds_json.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("folds JSON must contain an array")
    folds = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise TypeError(f"fold {index} must be an object")
        folds.append(
            PolicyFold(
                baseline_version=str(item["baseline_version"]),
                candidate_version=str(item["candidate_version"]),
                marketplace=str(item["marketplace"]),
                train_cutoff=_time(str(item["train_cutoff"])),
                evaluation_end=_time(str(item["evaluation_end"])),
            )
        )
    with LearningStore(args.database) as store:
        report = walk_forward_backtest(
            store,
            folds,
            evaluated_at=args.evaluated_at,
            policy=_backtest_policy(args),
        )
    _write_json(report.to_dict(), args.output)
    return 0 if report.promotion_eligible else 2


def _policy_decision(args: argparse.Namespace) -> int:
    with LearningStore(args.database) as store:
        decision_id = store.record_policy_decision(
            baseline_version=args.baseline_version,
            candidate_version=args.candidate_version,
            evaluation_digest=args.evaluation_digest,
            decision=args.decision,
            actor=args.actor,
            reason=args.reason,
            created_at=args.created_at,
        )
    _write_json({"decision_id": decision_id, "decision": args.decision})
    return 0


def _add_reporting_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--reporting-lag-days", type=int, default=7)


def _add_backtest_args(parser: argparse.ArgumentParser) -> None:
    _add_reporting_args(parser)
    parser.add_argument("--min-evaluation-forecasts", type=int, default=10)
    parser.add_argument("--min-candidate-selections", type=int, default=3)
    parser.add_argument("--max-relative-ev-regression", type=float, default=0.05)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="affiliate-mate-learning",
        description=(
            "Freeze forecasts before outcomes, import realized reports, calibrate assumptions, "
            "and evaluate scoring-policy changes without future leakage."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("database", type=Path)
    init.set_defaults(handler=_init)

    register = sub.add_parser("policy-register")
    register.add_argument("database", type=Path)
    register.add_argument("version")
    register.add_argument("--policy-json", type=Path)
    register.add_argument("--created-at", type=_time, required=True)
    register.add_argument("--parent-version")
    register.add_argument("--notes", default="")
    register.set_defaults(handler=_policy_register)

    forecast = sub.add_parser("forecast")
    forecast.add_argument("database", type=Path)
    forecast.add_argument("products_csv", type=Path)
    forecast.add_argument("product_id")
    forecast.add_argument("--policy-version", required=True)
    forecast.add_argument("--content-id", required=True)
    forecast.add_argument("--category", required=True)
    forecast.add_argument("--predicted-at", type=_time, required=True)
    forecast.add_argument("--horizon-days", type=int, default=30)
    forecast.add_argument("--package-digest")
    forecast.add_argument("--evidence-db", type=Path)
    forecast.add_argument("--min-evidence-confidence", type=float, default=0.0)
    forecast.add_argument("--output", type=Path)
    forecast.set_defaults(handler=_forecast)

    video = sub.add_parser("import-video")
    video.add_argument("database", type=Path)
    video.add_argument("csv", type=Path)
    video.add_argument("--ingested-at", type=_time, required=True)
    video.add_argument("--source", default="youtube-export")
    video.set_defaults(handler=_import_video)

    affiliate = sub.add_parser("import-affiliate")
    affiliate.add_argument("database", type=Path)
    affiliate.add_argument("csv", type=Path)
    affiliate.add_argument("--ingested-at", type=_time, required=True)
    affiliate.add_argument("--source", default="affiliate-export")
    affiliate.set_defaults(handler=_import_affiliate)

    performance = sub.add_parser("performance")
    performance.add_argument("database", type=Path)
    performance.add_argument("forecast_id")
    performance.add_argument("--evaluated-at", type=_time, required=True)
    _add_reporting_args(performance)
    performance.add_argument("--output", type=Path)
    performance.set_defaults(handler=_performance)

    calibrate = sub.add_parser("calibrate")
    calibrate.add_argument("database", type=Path)
    calibrate.add_argument("--evaluated-at", type=_time, required=True)
    calibrate.add_argument("--start", type=_time)
    calibrate.add_argument("--end", type=_time)
    calibrate.add_argument("--marketplace")
    _add_reporting_args(calibrate)
    calibrate.add_argument("--min-forecasts", type=int, default=3)
    calibrate.add_argument("--min-views", type=int, default=1000)
    calibrate.add_argument("--min-clicks", type=int, default=50)
    calibrate.add_argument("--min-orders", type=int, default=5)
    calibrate.add_argument("--relative-drift-threshold", type=float, default=0.25)
    calibrate.add_argument("--output", type=Path)
    calibrate.set_defaults(handler=_calibrate)

    backtest = sub.add_parser("backtest")
    backtest.add_argument("database", type=Path)
    backtest.add_argument("baseline_version")
    backtest.add_argument("candidate_version")
    backtest.add_argument("marketplace")
    backtest.add_argument("--train-cutoff", type=_time, required=True)
    backtest.add_argument("--evaluation-end", type=_time, required=True)
    backtest.add_argument("--evaluated-at", type=_time, required=True)
    _add_backtest_args(backtest)
    backtest.add_argument("--output", type=Path)
    backtest.set_defaults(handler=_backtest)

    walk = sub.add_parser("walk-forward")
    walk.add_argument("database", type=Path)
    walk.add_argument("folds_json", type=Path)
    walk.add_argument("--evaluated-at", type=_time, required=True)
    _add_backtest_args(walk)
    walk.add_argument("--output", type=Path)
    walk.set_defaults(handler=_walk_forward)

    decision = sub.add_parser("policy-decision")
    decision.add_argument("database", type=Path)
    decision.add_argument("baseline_version")
    decision.add_argument("candidate_version")
    decision.add_argument("evaluation_digest")
    decision.add_argument("decision", choices=("approve", "reject"))
    decision.add_argument("--actor", required=True)
    decision.add_argument("--reason", required=True)
    decision.add_argument("--created-at", type=_time, required=True)
    decision.set_defaults(handler=_policy_decision)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
