import json

import pytest

from affiliate_mate.catalog_cli import main


def test_mock_search_json(capsys):
    assert main(["mock-search", "camera", "--marketplace", "DE", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["product_id"] == "MOCK-DE-CAM-001"
    assert payload[0]["currency"] == "EUR"


def test_commission_lookup(tmp_path, capsys):
    path = tmp_path / "rates.csv"
    path.write_text(
        "marketplace,category,commission_rate\nDE,Electronics,0.03\n",
        encoding="utf-8",
    )
    assert main(["commission-lookup", str(path), "DE", "Electronics"]) == 0
    assert "3.00%" in capsys.readouterr().out


def test_cli_rejects_invalid_limit():
    with pytest.raises(SystemExit, match="between 1 and 10"):
        main(["mock-search", "camera", "--limit", "11"])
