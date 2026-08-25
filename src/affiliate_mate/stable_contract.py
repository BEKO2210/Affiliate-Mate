"""Public v1 compatibility and performance contracts.

The contract is deliberately data-only so automation can inspect what Affiliate-Mate
commits to supporting without importing optional adapters or touching a workspace.
"""

from __future__ import annotations

from . import __version__
from .analysis import ANALYSIS_SCHEMA_VERSION
from .exit_codes import EXIT_CODE_SCHEMA_VERSION
from .learning_models import (
    BACKTEST_SCHEMA_VERSION,
    CALIBRATION_SCHEMA_VERSION,
    FORECAST_SCHEMA_VERSION,
    OUTCOME_SCHEMA_VERSION,
    PERFORMANCE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    WALK_FORWARD_SCHEMA_VERSION,
)
from .production_models import (
    PRODUCTION_AUTH_SCHEMA_VERSION,
    PRODUCTION_PACKAGE_SCHEMA_VERSION,
    PRODUCTION_SIGNOFF_SCHEMA_VERSION,
    PUBLISH_PLAN_SCHEMA_VERSION,
    SCRIPT_SCHEMA_VERSION,
)
from .research_brief import RESEARCH_BRIEF_SCHEMA_VERSION
from .workspace import WORKSPACE_SCHEMA_VERSION

COMPATIBILITY_SCHEMA_VERSION = "affiliate-mate.compatibility.v1"
PERFORMANCE_BUDGET_SCHEMA_VERSION = "affiliate-mate.performance-budget.v1"

_COMPATIBILITY_SHIMS = (
    "affiliate-mate-catalog",
    "affiliate-mate-intel",
    "affiliate-mate-research",
    "affiliate-mate-production",
    "affiliate-mate-learning",
    "affiliate-mate-ops",
)


def compatibility_contract() -> dict[str, object]:
    """Return the machine-readable compatibility promise for Affiliate-Mate 1.x."""

    return {
        "schema_version": COMPATIBILITY_SCHEMA_VERSION,
        "package_version": __version__,
        "stable_major": 1,
        "semver_policy": (
            "Within 1.x, backwards-incompatible public CLI or serialized-contract changes "
            "require a new major version unless a versioned migration path preserves old input."
        ),
        "primary_cli": "affiliate-mate",
        "compatibility_shims": list(_COMPATIBILITY_SHIMS),
        "workspace_schema": WORKSPACE_SCHEMA_VERSION,
        "machine_contracts": {
            "analysis": ANALYSIS_SCHEMA_VERSION,
            "research_brief": RESEARCH_BRIEF_SCHEMA_VERSION,
            "production_authorization": PRODUCTION_AUTH_SCHEMA_VERSION,
            "script": SCRIPT_SCHEMA_VERSION,
            "production_package": PRODUCTION_PACKAGE_SCHEMA_VERSION,
            "production_signoff": PRODUCTION_SIGNOFF_SCHEMA_VERSION,
            "publish_plan": PUBLISH_PLAN_SCHEMA_VERSION,
            "outcome_event": OUTCOME_SCHEMA_VERSION,
            "forecast_snapshot": FORECAST_SCHEMA_VERSION,
            "scoring_policy": POLICY_SCHEMA_VERSION,
            "performance_report": PERFORMANCE_SCHEMA_VERSION,
            "calibration_report": CALIBRATION_SCHEMA_VERSION,
            "backtest_report": BACKTEST_SCHEMA_VERSION,
            "walk_forward_report": WALK_FORWARD_SCHEMA_VERSION,
            "exit_codes": EXIT_CODE_SCHEMA_VERSION,
        },
        "guarantees": {
            "unknown_schema_versions_fail_closed": True,
            "live_publishing_default": False,
            "human_research_approval_required": True,
            "human_production_signoff_required": True,
            "policy_promotion_is_never_automatic": True,
            "credential_free_demo_path": True,
        },
    }


def performance_budget_contract() -> dict[str, object]:
    """Return conservative budgets used by the stable acceptance path."""

    return {
        "schema_version": PERFORMANCE_BUDGET_SCHEMA_VERSION,
        "package_version": __version__,
        "golden_acceptance": {
            "max_wall_seconds": 20.0,
            "network_required": False,
            "credentials_required": False,
        },
        "operational_defaults": {
            "http_retry_attempts_max": 4,
            "search_items_limit_max": 10,
            "external_side_effects_in_acceptance": 0,
        },
    }
