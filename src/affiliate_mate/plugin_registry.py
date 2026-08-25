"""Capability introspection for built-in and external Affiliate-Mate adapters."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata

PLUGIN_ENTRYPOINT_GROUP = "affiliate_mate.plugins"
PLUGIN_REGISTRY_SCHEMA_VERSION = "affiliate-mate.plugins.v1"
PLUGIN_HEALTH_SCHEMA_VERSION = "affiliate-mate.plugin-health.v1"


class PluginCapability(StrEnum):
    CATALOG = "catalog"
    INTELLIGENCE = "intelligence"
    RESEARCH = "research"
    PRODUCTION = "production"
    LEARNING = "learning"
    OPERATIONS = "operations"
    PUBLISHING = "publishing"
    DIAGNOSTICS = "diagnostics"


class PluginHealthStatus(StrEnum):
    READY = "ready"
    WARN = "warn"
    BLOCKED = "blocked"
    METADATA_ONLY = "metadata-only"


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    name: str
    provider: str
    capabilities: tuple[PluginCapability, ...]
    source: str
    import_target: str
    installed: bool = True
    trusted_builtin: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("plugin name must not be empty")
        if not self.provider.strip():
            raise ValueError("plugin provider must not be empty")
        if not self.import_target.strip():
            raise ValueError("plugin import_target must not be empty")
        if not self.capabilities:
            raise ValueError("plugin must declare at least one capability")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("plugin capabilities must be unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "provider": self.provider,
            "capabilities": sorted(capability.value for capability in self.capabilities),
            "source": self.source,
            "import_target": self.import_target,
            "installed": self.installed,
            "trusted_builtin": self.trusted_builtin,
        }


@dataclass(frozen=True, slots=True)
class PluginHealth:
    name: str
    status: PluginHealthStatus
    message: str
    missing_requirements: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "missing_requirements": list(self.missing_requirements),
        }


_BUILTINS = (
    PluginDescriptor(
        name="mock-catalog",
        provider="affiliate-mate",
        capabilities=(PluginCapability.CATALOG, PluginCapability.DIAGNOSTICS),
        source="builtin",
        import_target="affiliate_mate.mock_catalog",
        trusted_builtin=True,
    ),
    PluginDescriptor(
        name="amazon-creators",
        provider="amazon",
        capabilities=(PluginCapability.CATALOG, PluginCapability.DIAGNOSTICS),
        source="builtin",
        import_target="affiliate_mate.amazon_creators",
        trusted_builtin=True,
    ),
    PluginDescriptor(
        name="youtube-intelligence",
        provider="youtube",
        capabilities=(PluginCapability.INTELLIGENCE, PluginCapability.DIAGNOSTICS),
        source="builtin",
        import_target="affiliate_mate.youtube_intelligence",
        trusted_builtin=True,
    ),
    PluginDescriptor(
        name="keyword-intelligence",
        provider="affiliate-mate",
        capabilities=(PluginCapability.INTELLIGENCE,),
        source="builtin",
        import_target="affiliate_mate.keyword_intelligence",
        trusted_builtin=True,
    ),
    PluginDescriptor(
        name="trend-intelligence",
        provider="affiliate-mate",
        capabilities=(PluginCapability.INTELLIGENCE,),
        source="builtin",
        import_target="affiliate_mate.trend_intelligence",
        trusted_builtin=True,
    ),
    PluginDescriptor(
        name="production-adapters",
        provider="affiliate-mate",
        capabilities=(PluginCapability.PRODUCTION, PluginCapability.PUBLISHING),
        source="builtin",
        import_target="affiliate_mate.production_adapters",
        trusted_builtin=True,
    ),
)

_SECRET_REQUIREMENTS = {
    "amazon-creators": (
        "AMAZON_CREATORS_CREDENTIAL_ID",
        "AMAZON_CREATORS_CREDENTIAL_SECRET",
        "AMAZON_ASSOCIATE_TAG",
    ),
    "youtube-intelligence": ("YOUTUBE_API_KEY",),
}


def builtin_plugins() -> tuple[PluginDescriptor, ...]:
    return _BUILTINS


def _external_entry_points() -> Iterable[metadata.EntryPoint]:
    discovered = metadata.entry_points()
    if hasattr(discovered, "select"):
        return discovered.select(group=PLUGIN_ENTRYPOINT_GROUP)
    return discovered.get(PLUGIN_ENTRYPOINT_GROUP, ())


def discover_plugins(*, include_external: bool = True) -> tuple[PluginDescriptor, ...]:
    """List plugins without importing third-party plugin code.

    External entry points are metadata-only descriptors. They are intentionally
    not loaded during discovery; executing third-party code is a separate trust
    decision for future adapter activation.
    """

    plugins = list(_BUILTINS)
    if include_external:
        for entry_point in _external_entry_points():
            plugins.append(
                PluginDescriptor(
                    name=entry_point.name,
                    provider="external",
                    capabilities=(PluginCapability.DIAGNOSTICS,),
                    source="entry-point",
                    import_target=entry_point.value,
                    trusted_builtin=False,
                )
            )
    plugins.sort(key=lambda item: (item.source != "builtin", item.name, item.import_target))
    return tuple(plugins)


def diagnose_plugins(
    *,
    env: Mapping[str, str] | None = None,
    include_external: bool = True,
) -> tuple[PluginHealth, ...]:
    """Evaluate adapter readiness without exposing secret values or loading external code."""

    values = os.environ if env is None else env
    results: list[PluginHealth] = []
    for plugin in discover_plugins(include_external=include_external):
        if not plugin.trusted_builtin:
            results.append(
                PluginHealth(
                    name=plugin.name,
                    status=PluginHealthStatus.METADATA_ONLY,
                    message="External plugin discovered but not loaded during diagnostics.",
                )
            )
            continue
        requirements = _SECRET_REQUIREMENTS.get(plugin.name, ())
        missing = tuple(name for name in requirements if not values.get(name, "").strip())
        if missing:
            results.append(
                PluginHealth(
                    name=plugin.name,
                    status=PluginHealthStatus.BLOCKED,
                    message="Required provider credentials are not present; values were not read out.",
                    missing_requirements=missing,
                )
            )
            continue
        if plugin.name == "production-adapters":
            results.append(
                PluginHealth(
                    name=plugin.name,
                    status=PluginHealthStatus.WARN,
                    message=(
                        "Dry-run production adapters are available; live publishing remains "
                        "an explicit operational opt-in."
                    ),
                )
            )
            continue
        results.append(
            PluginHealth(
                name=plugin.name,
                status=PluginHealthStatus.READY,
                message="Adapter prerequisites are satisfied for its credential-free surface.",
            )
        )
    return tuple(results)


def plugin_registry_payload(*, include_external: bool = True) -> dict[str, object]:
    plugins = discover_plugins(include_external=include_external)
    return {
        "schema_version": PLUGIN_REGISTRY_SCHEMA_VERSION,
        "entrypoint_group": PLUGIN_ENTRYPOINT_GROUP,
        "plugins": [plugin.to_dict() for plugin in plugins],
    }


def plugin_health_payload(
    *,
    env: Mapping[str, str] | None = None,
    include_external: bool = True,
) -> dict[str, object]:
    health = diagnose_plugins(env=env, include_external=include_external)
    blocked = sum(item.status is PluginHealthStatus.BLOCKED for item in health)
    return {
        "schema_version": PLUGIN_HEALTH_SCHEMA_VERSION,
        "healthy": blocked == 0,
        "blocked": blocked,
        "plugins": [item.to_dict() for item in health],
    }
