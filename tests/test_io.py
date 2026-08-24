from affiliate_mate.io import load_candidate_inputs_csv, load_candidates_csv


def test_load_candidates_csv(tmp_path):
    source = tmp_path / "products.csv"
    source.write_text(
        "product_id,title,price,commission_rate,monthly_searches\n"
        "x1,Widget,199.99,0.03,500\n",
        encoding="utf-8",
    )
    rows = load_candidates_csv(source)
    assert len(rows) == 1
    assert rows[0].product_id == "x1"
    assert rows[0].commission_per_sale == 199.99 * 0.03


def test_missing_required_columns(tmp_path):
    source = tmp_path / "broken.csv"
    source.write_text("product_id,title\nx1,Widget\n", encoding="utf-8")
    try:
        load_candidates_csv(source)
    except ValueError as exc:
        assert "commission_rate" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_candidate_input_tracks_only_explicit_non_empty_fields(tmp_path):
    source = tmp_path / "products.csv"
    source.write_text(
        "product_id,title,price,commission_rate,monthly_searches,evidence_quality\n"
        "x1,Widget,100,0.04,500,\n",
        encoding="utf-8",
    )
    item = load_candidate_inputs_csv(source)[0]
    assert "monthly_searches" in item.provided_fields
    assert "evidence_quality" not in item.provided_fields
