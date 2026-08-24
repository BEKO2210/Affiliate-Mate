from affiliate_mate.io import load_candidates_csv


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
