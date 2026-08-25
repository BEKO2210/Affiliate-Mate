from affiliate_mate.plugin_registry import (
    PLUGIN_HEALTH_SCHEMA_VERSION,
    PLUGIN_REGISTRY_SCHEMA_VERSION,
    PluginCapability,
    PluginHealthStatus,
    builtin_plugins,
    diagnose_plugins,
    discover_plugins,
    plugin_health_payload,
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


def test_adapter_doctor_blocks_missing_provider_credentials_without_values() -> None:
    health = diagnose_plugins(env={}, include_external=False)
    by_name = {item.name: item for item in health}

    assert by_name["mock-catalog"].status is PluginHealthStatus.READY
    assert by_name["amazon-creators"].status is PluginHealthStatus.BLOCKED
    assert "AMAZON_CREATORS_CREDENTIAL_SECRET" in by_name["amazon-creators"].missing_requirements
    assert by_name["youtube-intelligence"].status is PluginHealthStatus.BLOCKED
    assert by_name["production-adapters"].status is PluginHealthStatus.WARN


def test_adapter_doctor_becomes_ready_when_required_secret_names_are_present() -> None:
    env = {
        "AMAZON_CREATORS_CREDENTIAL_ID": "id-value",
        "AMAZON_CREATORS_CREDENTIAL_SECRET": "secret-value",
        "AMAZON_ASSOCIATE_TAG": "tag-value",
        "YOUTUBE_API_KEY": "youtube-value",
    }
    payload = plugin_health_payload(env=env, include_external=False)

    assert payload["schema_version"] == PLUGIN_HEALTH_SCHEMA_VERSION
    assert payload["blocked"] == 0
    serialized = str(payload)
    assert "secret-value" not in serialized
    assert "youtube-value" not in serialized
