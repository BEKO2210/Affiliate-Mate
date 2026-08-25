from affiliate_mate import __version__
from affiliate_mate.release_channel import ReleaseChannel, resolve_release_channel
from affiliate_mate.stable_contract import compatibility_contract, performance_budget_contract


def test_v1_package_defaults_to_stable_channel() -> None:
    assert __version__ == "1.0.0"
    state = resolve_release_channel(env={})
    assert state.channel is ReleaseChannel.STABLE
    assert state.publishing_allowed is True


def test_compatibility_contract_freezes_public_v1_surface() -> None:
    contract = compatibility_contract()
    assert contract["schema_version"] == "affiliate-mate.compatibility.v1"
    assert contract["stable_major"] == 1
    assert contract["primary_cli"] == "affiliate-mate"
    assert len(contract["compatibility_shims"]) == 6
    assert contract["machine_contracts"]["analysis"] == "affiliate-mate.analysis.v1"
    assert contract["machine_contracts"]["production_package"] == "affiliate-mate.production-package.v1"
    assert contract["guarantees"]["unknown_schema_versions_fail_closed"] is True
    assert contract["guarantees"]["policy_promotion_is_never_automatic"] is True


def test_performance_budget_is_credential_and_network_free() -> None:
    budget = performance_budget_contract()
    golden = budget["golden_acceptance"]
    assert golden["max_wall_seconds"] >= 1
    assert golden["network_required"] is False
    assert golden["credentials_required"] is False
    assert budget["operational_defaults"]["external_side_effects_in_acceptance"] == 0
