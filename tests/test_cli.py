import json
from datetime import UTC, datetime

from affiliate_mate.cli import main

CSV = (
    "product_id,title,marketplace,currency,price,commission_rate,monthly_searches,"
    "youtube_competition,buyer_intent,content_gap,evidence_quality,estimated_ctr,"
    "estimated_conversion_rate\n"
    "strong,Strong Product,DE,EUR,350,0.05,5000,25,90,80,90,0.05,0.03\n"
    "weak,Weak Product,DE,EUR,50,0.01,10,99,10,10,20,0.01,0.01\n"
)


def test_analyze_json_output_is_machine_readable(tmp_path, capsys):
    source = tmp_path / "products.csv"
    source.write_text(CSV, encoding="utf-8")
    code = main(["analyze", str(source), "--format", "json", "--include-rejected"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "affiliate-mate.analysis.v1"
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["shortlisted"] == 1


def test_analyze_table_defaults_to_shortlist_only(tmp_path, capsys):
    source = tmp_path / "products.csv"
    source.write_text(CSV, encoding="utf-8")
    assert main(["analyze", str(source)]) == 0
    output = capsys.readouterr().out
    assert "Strong Product" in output
    assert "Weak Product" not in output


def test_evidence_cli_init_add_and_latest_json(tmp_path, capsys):
    db = tmp_path / "evidence.sqlite3"
    assert main(["evidence", "init", str(db)]) == 0
    capsys.readouterr()

    observed = datetime(2026, 8, 25, 10, 0, tzinfo=UTC).isoformat()
    assert (
        main(
            [
                "evidence",
                "add",
                str(db),
                "p1",
                "monthly_searches",
                "1234",
                "--source",
                "manual",
                "--observed-at",
                observed,
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "evidence",
                "latest",
                str(db),
                "p1",
                "monthly_searches",
                "--as-of",
                "2026-08-25T11:00:00Z",
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["value"] == 1234.0
    assert payload["source"] == "manual"


def test_evidence_latest_returns_nonzero_when_missing(tmp_path, capsys):
    db = tmp_path / "evidence.sqlite3"
    code = main(["evidence", "latest", str(db), "missing", "price"])
    assert code == 1
    assert "No matching observation" in capsys.readouterr().out


def test_analyze_can_apply_persisted_evidence(tmp_path, capsys):
    from affiliate_mate.evidence import EvidenceObservation, SQLiteEvidenceStore

    source = tmp_path / "products.csv"
    source.write_text(
        "product_id,title,marketplace,currency,price,commission_rate,monthly_searches,"
        "youtube_competition,buyer_intent,content_gap,evidence_quality,estimated_ctr,"
        "estimated_conversion_rate\n"
        "p1,Product,DE,EUR,350,0.05,5000,25,90,80,,0.05,0.03\n",
        encoding="utf-8",
    )
    db = tmp_path / "evidence.sqlite3"
    observed = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    with SQLiteEvidenceStore(db) as store:
        store.add(
            EvidenceObservation(
                product_id="p1",
                signal="evidence_quality",
                value=90,
                source="manual-audit",
                observed_at=observed,
            )
        )
    code = main(
        [
            "analyze",
            str(source),
            "--format",
            "json",
            "--evidence-db",
            str(db),
            "--as-of",
            "2026-08-25T11:00:00Z",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["shortlisted"] == 1
    resolution = payload["results"][0]["evidence_resolution"]
    assert resolution["applied"][0]["signal"] == "evidence_quality"
