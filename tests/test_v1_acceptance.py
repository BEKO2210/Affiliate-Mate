from affiliate_mate.acceptance import run_golden_acceptance


def test_v1_golden_acceptance_spans_full_trust_chain(tmp_path) -> None:
    report = run_golden_acceptance(tmp_path)

    assert report["passed"] is True
    assert report["credential_free"] is True
    assert report["network_calls"] == 0
    assert report["candidate"]["accepted"] is True
    assert report["research"]["approved"] is True
    assert report["production"]["signoff_bound"] is True
    assert report["production"]["publish_dry_run_ready"] is True
    assert report["production"]["side_effecting"] is False
    assert report["learning"]["sample_eligible"] is True
