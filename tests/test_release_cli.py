import json
from datetime import UTC, datetime

from affiliate_mate.exit_codes import ExitCode
from affiliate_mate.release_cli import main


def test_release_cli_verifies_stable_install(capsys) -> None:
    assert main(["verify"]) == ExitCode.OK
    report = json.loads(capsys.readouterr().out)
    assert report["version"] == "1.0.0"
    assert report["passed"] is True


def test_release_cli_contract_and_budget(capsys) -> None:
    assert main(["contract"]) == ExitCode.OK
    contract = json.loads(capsys.readouterr().out)
    assert contract["stable_major"] == 1

    assert main(["performance-budget"]) == ExitCode.OK
    budget = json.loads(capsys.readouterr().out)
    assert budget["golden_acceptance"]["network_required"] is False


def test_release_cli_manifest_roundtrip(tmp_path, capsys) -> None:
    artifact = tmp_path / "artifact.whl"
    manifest = tmp_path / "manifest.json"
    artifact.write_bytes(b"release")
    stamp = datetime(2026, 8, 25, tzinfo=UTC).isoformat()

    assert main(
        [
            "manifest",
            str(artifact),
            "--root",
            str(tmp_path),
            "--commit-sha",
            "d" * 40,
            "--created-at",
            stamp,
            "--output",
            str(manifest),
        ]
    ) == ExitCode.OK
    assert capsys.readouterr().out == ""

    assert main(["manifest-verify", str(manifest), "--root", str(tmp_path)]) == ExitCode.OK
    report = json.loads(capsys.readouterr().out)
    assert report["passed"] is True
