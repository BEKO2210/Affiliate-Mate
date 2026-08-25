"""Capability introspection for built-in and external Affiliate-Mate adapters."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata

PLUGIN_ENTRYPOINT_GROUP = "affiliate_mate.plugins"
PLUGIN_REGISTRY_SCHEMA_VERSION = "affiliate-mate.plugins.v1"


class PluginCapability(StrEnum):
    CATALOG = "catalog"
    INTELLIGENCE = "intelligence"
    RESEARCH = "research"
    PRODUCTION = "production"
    LEARNING = "learning"
    OPERATIONS = "operations"
    PUBLISHING = "publishing"
    DIAGNOSTICS = "diagnostics"


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


def plugin_registry_payload(*, include_external: bool = True) -> dict[str, object]:
    plugins = discover_plugins(include_external=include_external)
    return {
        "schema_version": PLUGIN_REGISTRY_SCHEMA_VERSION,
        "entrypoint_group": PLUGIN_ENTRYPOINT_GROUP,
        "plugins": [plugin.to_dict() for plugin in plugins],
    }
