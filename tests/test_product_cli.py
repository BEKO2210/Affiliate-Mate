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
    assert "compatibility" in help_output.lower()

    assert main(["--version"]) == ExitCode.OK
    assert capsys.readouterr().out.strip() == __version__


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

    assert main(["contract", "exit-codes"]) == ExitCode.OK
    contract = json.loads(capsys.readouterr().out)
    assert contract["codes"]["0"] == "success"
    assert contract["codes"]["70"] == "unexpected internal error"


def test_unknown_command_has_stable_configuration_error(capsys) -> None:
    assert main(["definitely-not-a-command"]) == ExitCode.CONFIG_ERROR
    captured = capsys.readouterr()
    assert "unknown command" in captured.err


def test_shell_completion_is_generated_without_extra_dependency(capsys) -> None:
    assert main(["completion", "bash"]) == ExitCode.OK
    output = capsys.readouterr().out
    assert "complete -F _affiliate_mate affiliate-mate" in output
    assert "workspace" in output
