import json
from pathlib import Path

from affiliate_mate import __version__
from affiliate_mate.exit_codes import ExitCode
from affiliate_mate.product_cli import main


def test_product_cli_help_and_version(capsys) -> None:
    assert main(["--help"]) == ExitCode.OK
    help_output = capsys.readouterr().out
    assert "workspace" in help_output
    assert "catalog" in help_output
    assert "upgrade" in help_output
    assert "compatibility" in help_output.lower()

    assert main(["--version"]) == ExitCode.OK
    assert capsys.readouterr().out.strip() == __version__


def test_guided_init_plan_is_side_effect_free(tmp_path: Path, capsys) -> None:
    root = tmp_path / "planned"
    assert main(["init", str(root), "--plan", "--profile", "creator"]) == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)

    assert payload["profile"] == "creator"
    assert payload["release"]["channel"] == "stable"
    assert payload["stores_secrets"] is False
    assert not root.exists()


def test_workspace_init_show_and_status(tmp_path: Path, capsys, monkeypatch) -> None:
    assert main(["workspace", "init", str(tmp_path), "--profile", "creator"]) == ExitCode.OK
    init_payload = json.loads(capsys.readouterr().out)
    assert init_payload["manifest"]["active_profile"] == "creator"

    assert main(["workspace", "show", str(tmp_path)]) == ExitCode.OK
    shown = json.loads(capsys.readouterr().out)
    assert shown["manifest"]["profiles"][0]["name"] == "creator"

    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    assert main(["status", "--format", "json"]) == ExitCode.OK
    status = json.loads(capsys.readouterr().out)
    assert status["profile"] == "creator"
    assert status["paths"]["manifest"]["exists"] is True
    assert status["paths"]["database"]["exists"] is False


def test_demo_init_creates_immediately_analyzable_csv(tmp_path: Path, capsys) -> None:
    root = tmp_path / "demo"
    assert main(["demo", "init", str(root)]) == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)

    assert Path(payload["candidate_csv"]).is_file()
    assert "affiliate-mate analyze" in payload["next"]


def test_plugins_and_exit_code_contract_are_machine_readable(capsys) -> None:
    assert main(["plugins", "list", "--builtin-only", "--format", "json"]) == ExitCode.OK
    plugins = json.loads(capsys.readouterr().out)
    assert plugins["plugins"]
    assert all(plugin["trusted_builtin"] for plugin in plugins["plugins"])

    assert main(["plugins", "doctor", "--builtin-only", "--format", "json"]) in {
        ExitCode.OK,
        ExitCode.CHECK_FAILED,
    }
    health = json.loads(capsys.readouterr().out)
    assert "blocked" in health
    serialized = json.dumps(health)
    assert "secret-value" not in serialized

    assert main(["contract", "exit-codes"]) == ExitCode.OK
    contract = json.loads(capsys.readouterr().out)
    assert contract["codes"]["0"] == "success"
    assert contract["codes"]["70"] == "unexpected internal error"


def test_release_and_config_reference_commands(capsys) -> None:
    assert main(["release", "channel", "--format", "json"]) == ExitCode.OK
    release = json.loads(capsys.readouterr().out)
    assert release["channel"] == "stable"
    assert release["publishing_allowed"] is True

    assert main(["config", "reference", "--format", "json"]) == ExitCode.OK
    reference = json.loads(capsys.readouterr().out)
    assert reference["config_schema_version"] == "affiliate-mate.config.v1"
    assert any(field["path"] == "database.path" for field in reference["fields"])


def test_upgrade_plan_and_apply_through_primary_cli(tmp_path: Path, capsys, monkeypatch) -> None:
    assert main(["workspace", "init", str(tmp_path)]) == ExitCode.OK
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)

    assert main(["upgrade", "plan"]) == ExitCode.OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["changes_required"] is True
    assert plan["blocked"] is False

    assert main(["upgrade", "apply"]) == ExitCode.CHECK_FAILED
    assert "explicit confirmation" in capsys.readouterr().err

    assert main(["upgrade", "apply", "--yes"]) == ExitCode.OK
    result = json.loads(capsys.readouterr().out)
    assert result["applied"] is True

    assert main(["upgrade", "plan"]) == ExitCode.OK
    final_plan = json.loads(capsys.readouterr().out)
    assert final_plan["changes_required"] is False


def test_workspace_doctor_resolves_paths_from_nested_directory(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    assert main(["workspace", "init", str(tmp_path)]) == ExitCode.OK
    capsys.readouterr()
    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)

    assert main(["doctor", "--format", "json"]) == ExitCode.OK
    report = json.loads(capsys.readouterr().out)
    database = next(check for check in report["checks"] if check["code"] == "database.path")
    assert str(tmp_path / ".affiliate-mate" / "state.sqlite3") in database["message"]


def test_unknown_command_has_stable_configuration_error(capsys) -> None:
    assert main(["definitely-not-a-command"]) == ExitCode.CONFIG_ERROR
    captured = capsys.readouterr()
    assert "unknown command" in captured.err


def test_shell_completion_is_generated_without_extra_dependency(capsys) -> None:
    assert main(["completion", "bash"]) == ExitCode.OK
    output = capsys.readouterr().out
    assert "complete -F _affiliate_mate affiliate-mate" in output
    assert "workspace" in output
    assert "upgrade" in output
