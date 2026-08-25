import json

from affiliate_mate.evidence import SQLiteEvidenceStore
from affiliate_mate.intelligence_cli import main


def _write_candidates(path) -> None:
    path.write_text(
        "product_id,title,marketplace,currency,price,commission_rate,monthly_searches,"
        "youtube_competition,buyer_intent,content_gap,evidence_quality\n"
        "p1,Example Camera,DE,EUR,199,0.03,100,50,50,50,80\n",
        encoding="utf-8",
    )


def test_collect_cli_persists_keyword_evidence(tmp_path, capsys) -> None:
    candidates = tmp_path / "products.csv"
    keywords = tmp_path / "keywords.csv"
    db = tmp_path / "evidence.sqlite3"
    _write_candidates(candidates)
    keywords.write_text(
        "product_id,marketplace,monthly_searches,buyer_intent,observed_at\n"
        "p1,DE,2400,82,2026-08-20T00:00:00Z\n",
        encoding="utf-8",
    )
    exit_code = main(
        [
            "collect",
            str(candidates),
            str(db),
            "--keyword-csv",
            str(keywords),
            "--format",
            "json",
        ]
    )
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["reports"][0]["observations_stored"] == 2
    with SQLiteEvidenceStore(db) as store:
        searches = store.latest("p1", "monthly_searches", marketplace="DE")
    assert searches is not None and searches.value == 2400


def test_cluster_cli_emits_machine_readable_groups(tmp_path, capsys) -> None:
    candidates = tmp_path / "products.csv"
    candidates.write_text(
        "product_id,title,marketplace,currency,price,commission_rate,monthly_searches,"
        "youtube_competition,buyer_intent,content_gap,evidence_quality\n"
        "a,Example Camera Pro 4K,DE,EUR,199,0.03,100,50,50,50,80\n"
        "b,Example Camera Pro 4K Black,DE,EUR,209,0.03,100,50,50,50,80\n",
        encoding="utf-8",
    )
    assert main(["cluster", str(candidates), "--threshold", "0.7", "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["clusters"][0]["members"] == ["a", "b"]
