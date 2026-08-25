"""Stable machine-readable exit-code contract for Affiliate-Mate CLIs."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Public CLI process exit codes.

    Existing command behavior is preserved where practical: ``1`` remains a
    clean no-result condition and ``2`` remains a failed validation/health
    gate. Higher values distinguish configuration and state conflicts without
    conflating them with internal failures.
    """

    OK = 0
    NO_RESULT = 1
    CHECK_FAILED = 2
    CONFIG_ERROR = 3
    CONFLICT = 4
    NOT_FOUND = 5
    INTERNAL_ERROR = 70


EXIT_CODE_SCHEMA_VERSION = "affiliate-mate.exit-codes.v1"


def exit_code_contract() -> dict[str, object]:
    """Return the stable exit-code contract for humans and automation."""

    return {
        "schema_version": EXIT_CODE_SCHEMA_VERSION,
        "codes": {
            "0": "success",
            "1": "valid command completed with no matching/resulting item",
            "2": "health, verification, validation, or policy check failed",
            "3": "configuration or workspace input is invalid",
            "4": "immutable identity or optimistic-concurrency conflict",
            "5": "requested workspace, profile, plugin, or resource was not found",
            "70": "unexpected internal error",
        },
    }
