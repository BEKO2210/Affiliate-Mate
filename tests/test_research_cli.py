import json

from affiliate_mate.research_cli import main


def test_init_and_status_commands(tmp_path, capsys) -> None:
    database = tmp_path / "research.sqlite3"
    assert main(["init", str(database)]) == 0
    capsys.readouterr()
    assert main(["status", str(database), "p1"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["approval_state"] == "draft"
    assert payload["completeness"]["passed"] is False


def test_reviews_command_is_credential_free(tmp_path, capsys) -> None:
    reviews = tmp_path / "reviews.csv"
    reviews.write_text(
        "review_id,product_id,marketplace,rating,title,body,source\n"
        "r1,p1,DE,5,Battery,Excellent battery runtime all day,user-export\n"
        "r2,p1,DE,4,Battery,Great battery runtime for work,user-export\n",
        encoding="utf-8",
    )
    assert main(["reviews", str(reviews), "p1", "DE", "--threshold", "0.2"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_reviews"] == 2
    assert payload["themes"]


def test_brief_rejects_invalid_confidence(tmp_path) -> None:
    candidates = tmp_path / "products.csv"
    candidates.write_text(
        "product_id,title,price,commission_rate\n"
        "p1,Product,100,0.05\n",
        encoding="utf-8",
    )
    research_db = tmp_path / "research.sqlite3"
    try:
        main(
            [
                "brief",
                str(candidates),
                "p1",
                str(research_db),
                "--min-evidence-confidence",
                "1.5",
            ]
        )
    except SystemExit as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("expected invalid confidence to fail")
