import json

from affiliate_mate.doctor import CheckStatus, run_doctor
from affiliate_mate.ops_config import (
    AppConfig,
    DatabaseConfig,
    FeatureFlags,
    ObservabilityConfig,
)
from affiliate_mate.ops_store import OpsStore


def test_doctor_reports_missing_database_as_warning_when_parent_is_writable(tmp_path) -> None:
    config = AppConfig(database=DatabaseConfig(path=str(tmp_path / "missing.sqlite3")))
    report = run_doctor(config, env={})
    database = next(check for check in report.checks if check.code == "database.path")
    assert database.status is CheckStatus.WARN
    assert report.healthy
    assert report.exit_code == 0


def test_doctor_detects_initialized_ops_schema(tmp_path) -> None:
    database = tmp_path / "affiliate.sqlite3"
    with OpsStore(database):
        pass
    config = AppConfig(
        database=DatabaseConfig(path=str(database)),
        observability=ObservabilityConfig(jsonl_path=str(tmp_path / "events.jsonl")),
    )
    report = run_doctor(config, env={})
    by_code = {check.code: check for check in report.checks}
    assert by_code["sqlite.integrity"].status is CheckStatus.PASS
    assert by_code["sqlite.foreign_keys"].status is CheckStatus.PASS
    assert by_code["schema.ops"].status is CheckStatus.PASS
    assert report.healthy


def test_doctor_never_serializes_secret_values(tmp_path) -> None:
    secret = "top-secret-api-key"
    config = AppConfig(database=DatabaseConfig(path=str(tmp_path / "missing.sqlite3")))
    report = run_doctor(config, env={"YOUTUBE_API_KEY": secret})
    serialized = json.dumps(report.to_dict())
    assert secret not in serialized
    secret_check = next(
        check for check in report.checks if check.code == "secrets.optional_providers"
    )
    assert "1/4" in secret_check.message


def test_live_publishing_is_visible_as_warning(tmp_path) -> None:
    config = AppConfig(
        database=DatabaseConfig(path=str(tmp_path / "missing.sqlite3")),
        features=FeatureFlags(live_publishing=True),
    )
    report = run_doctor(config, env={})
    check = next(check for check in report.checks if check.code == "feature.live_publishing")
    assert check.status is CheckStatus.WARN
