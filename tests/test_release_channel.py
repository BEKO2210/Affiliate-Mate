import pytest

from affiliate_mate.release_channel import (
    RELEASE_CHANNEL_SCHEMA_VERSION,
    ReleaseChannel,
    ReleaseChannelError,
    resolve_release_channel,
)


def test_pre_one_version_defaults_to_beta() -> None:
    state = resolve_release_channel(version="0.9.0", env={})

    assert state.channel is ReleaseChannel.BETA
    assert state.source == "version-policy"
    assert state.publishing_allowed is False
    assert state.to_dict()["schema_version"] == RELEASE_CHANNEL_SCHEMA_VERSION


def test_dev_version_defaults_to_dev() -> None:
    state = resolve_release_channel(version="0.9.0.dev4", env={})
    assert state.channel is ReleaseChannel.DEV


def test_environment_can_select_dev_but_not_fake_stable() -> None:
    state = resolve_release_channel(version="0.9.0", env={"AFFILIATE_MATE_CHANNEL": "dev"})
    assert state.channel is ReleaseChannel.DEV
    assert state.source == "environment"

    with pytest.raises(ReleaseChannelError, match="cannot claim the stable channel"):
        resolve_release_channel(version="0.9.0", env={"AFFILIATE_MATE_CHANNEL": "stable"})


def test_stable_version_can_select_stable() -> None:
    state = resolve_release_channel("stable", version="1.0.0", env={})
    assert state.channel is ReleaseChannel.STABLE
    assert state.publishing_allowed is True
