"""Generated configuration-reference contract for product-facing tooling and docs."""

from __future__ import annotations

import json

from .ops_config import CONFIG_SCHEMA_VERSION

CONFIG_REFERENCE_SCHEMA_VERSION = "affiliate-mate.config-reference.v1"


def config_reference_payload() -> dict[str, object]:
    return {
        "schema_version": CONFIG_REFERENCE_SCHEMA_VERSION,
        "config_schema_version": CONFIG_SCHEMA_VERSION,
        "fields": [
            {
                "path": "database.path",
                "type": "string",
                "default": "affiliate-mate.sqlite3",
                "environment": "AFFILIATE_MATE_DB",
                "secret": False,
                "description": "SQLite database path.",
            },
            {
                "path": "features.live_publishing",
                "type": "boolean",
                "default": False,
                "environment": "AFFILIATE_MATE_LIVE_PUBLISHING",
                "secret": False,
                "description": "Explicit fail-closed opt-in for future live publishing.",
            },
            {
                "path": "observability.jsonl_path",
                "type": "string|null",
                "default": None,
                "environment": "AFFILIATE_MATE_TELEMETRY_JSONL",
                "secret": False,
                "description": "Optional local JSONL operational telemetry path.",
            },
        ],
        "provider_secrets": [
            "AMAZON_CREATORS_CREDENTIAL_ID",
            "AMAZON_CREATORS_CREDENTIAL_SECRET",
            "AMAZON_ASSOCIATE_TAG",
            "YOUTUBE_API_KEY",
        ],
        "rules": [
            "unknown configuration keys are rejected",
            "provider secrets are environment/secret-provider state, not workspace JSON",
            "live publishing defaults to disabled",
            "configuration migrations are explicit and versioned",
        ],
    }


def config_reference_markdown() -> str:
    payload = config_reference_payload()
    lines = [
        "# Configuration reference",
        "",
        f"Config schema: `{payload['config_schema_version']}`",
        "",
        "| Field | Type | Default | Environment |",
        "| --- | --- | --- | --- |",
    ]
    for field in payload["fields"]:
        default = json.dumps(field["default"])
        lines.append(
            f"| `{field['path']}` | `{field['type']}` | `{default}` | "
            f"`{field['environment']}` |"
        )
    lines.extend(
        [
            "",
            "Provider credentials are intentionally not configuration fields:",
            "",
        ]
    )
    lines.extend(f"- `{name}`" for name in payload["provider_secrets"])
    lines.extend(["", "## Rules", ""])
    lines.extend(f"- {rule}" for rule in payload["rules"])
    return "\n".join(lines) + "\n"
