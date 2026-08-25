"""Guided local onboarding without collecting or storing provider secrets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .release_channel import ReleaseChannelState, resolve_release_channel
from .workspace import Workspace, create_demo_workspace, create_workspace

ONBOARDING_SCHEMA_VERSION = "affiliate-mate.onboarding.v1"


@dataclass(frozen=True, slots=True)
class OnboardingPlan:
    root: Path
    profile: str
    marketplace: str
    demo: bool
    release: ReleaseChannelState

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": ONBOARDING_SCHEMA_VERSION,
            "root": str(self.root),
            "profile": self.profile,
            "marketplace": self.marketplace,
            "demo": self.demo,
            "release": self.release.to_dict(),
            "stores_secrets": False,
            "next_steps": list(self.next_steps),
        }

    @property
    def next_steps(self) -> tuple[str, ...]:
        if self.demo:
            return (
                "cd into the workspace",
                "run: affiliate-mate status",
                "run: affiliate-mate analyze data/products.csv --include-rejected",
                "run: affiliate-mate plugins doctor",
            )
        return (
            "cd into the workspace",
            "run: affiliate-mate upgrade plan",
            "run: affiliate-mate doctor",
            "run: affiliate-mate plugins doctor",
            "add provider credentials only through environment/secret-provider state when needed",
        )


def build_onboarding_plan(
    root: str | Path,
    *,
    profile: str = "default",
    marketplace: str = "DE",
    demo: bool = False,
    channel: str | None = None,
) -> OnboardingPlan:
    return OnboardingPlan(
        root=Path(root).expanduser().resolve(),
        profile=profile,
        marketplace=marketplace.upper(),
        demo=demo,
        release=resolve_release_channel(channel),
    )


def execute_onboarding(plan: OnboardingPlan, *, force: bool = False) -> Workspace:
    """Create the planned local workspace; never ask for or persist credentials."""

    if plan.demo:
        return create_demo_workspace(plan.root, force=force)
    return create_workspace(
        plan.root,
        profile_name=plan.profile,
        marketplace=plan.marketplace,
        force=force,
    )
