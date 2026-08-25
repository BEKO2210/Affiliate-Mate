from pathlib import Path

from affiliate_mate.onboarding import build_onboarding_plan, execute_onboarding
from affiliate_mate.release_channel import ReleaseChannel


def test_onboarding_plan_is_secret_free_and_stable(tmp_path: Path) -> None:
    plan = build_onboarding_plan(tmp_path, profile="creator", marketplace="de", demo=False)
    payload = plan.to_dict()

    assert payload["stores_secrets"] is False
    assert payload["release"]["channel"] == ReleaseChannel.STABLE.value
    assert payload["profile"] == "creator"
    assert payload["marketplace"] == "DE"
    assert any("secret-provider" in step for step in payload["next_steps"])


def test_onboarding_executes_standard_workspace(tmp_path: Path) -> None:
    plan = build_onboarding_plan(tmp_path, profile="creator", marketplace="DE")
    workspace = execute_onboarding(plan)

    assert workspace.profile.name == "creator"
    assert workspace.profile.marketplace == "DE"
    assert workspace.config_path.is_file()


def test_onboarding_executes_credential_free_demo(tmp_path: Path) -> None:
    plan = build_onboarding_plan(tmp_path, demo=True)
    workspace = execute_onboarding(plan)

    assert workspace.profile.name == "demo"
    assert (workspace.data_dir / "products.csv").is_file()
