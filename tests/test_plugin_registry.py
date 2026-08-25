from affiliate_mate.plugin_registry import (
    PLUGIN_REGISTRY_SCHEMA_VERSION,
    PluginCapability,
    builtin_plugins,
    discover_plugins,
    plugin_registry_payload,
)


def test_builtin_plugins_are_unique_and_capability_aware() -> None:
    plugins = builtin_plugins()
    names = [plugin.name for plugin in plugins]

    assert len(names) == len(set(names))
    assert any(PluginCapability.CATALOG in plugin.capabilities for plugin in plugins)
    assert any(PluginCapability.INTELLIGENCE in plugin.capabilities for plugin in plugins)
    assert any(PluginCapability.PRODUCTION in plugin.capabilities for plugin in plugins)
    assert all(plugin.trusted_builtin for plugin in plugins)


def test_builtin_only_discovery_is_deterministic() -> None:
    first = discover_plugins(include_external=False)
    second = discover_plugins(include_external=False)

    assert first == second
    assert [plugin.name for plugin in first] == sorted(plugin.name for plugin in first)


def test_registry_payload_is_machine_readable() -> None:
    payload = plugin_registry_payload(include_external=False)

    assert payload["schema_version"] == PLUGIN_REGISTRY_SCHEMA_VERSION
    assert payload["entrypoint_group"] == "affiliate_mate.plugins"
    assert payload["plugins"]
    assert all(item["source"] == "builtin" for item in payload["plugins"])
