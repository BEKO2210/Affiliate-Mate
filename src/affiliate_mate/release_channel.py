"""Explicit stable/beta/dev release-channel policy."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from . import __version__

RELEASE_CHANNEL_SCHEMA_VERSION = "affiliate-mate.release-channel.v1"
_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<suffix>.*)$")


class ReleaseChannel(StrEnum):
    STABLE = "stable"
    BETA = "beta"
    DEV = "dev"


class ReleaseChannelError(ValueError):
    """Raised when release-channel intent conflicts with the installed version."""


@dataclass(frozen=True, slots=True)
class ReleaseChannelState:
    channel: ReleaseChannel
    version: str
    source: str

    @property
    def publishing_allowed(self) -> bool:
        return self.channel is ReleaseChannel.STABLE

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": RELEASE_CHANNEL_SCHEMA_VERSION,
            "channel": self.channel.value,
            "version": self.version,
            "source": self.source,
            "publishing_allowed": self.publishing_allowed,
        }


def _version_default(version: str) -> ReleaseChannel:
    match = _VERSION_RE.fullmatch(version)
    if match is None:
        raise ReleaseChannelError(f"unsupported version format: {version}")
    major = int(match.group("major"))
    suffix = match.group("suffix").lower()
    if ".dev" in suffix or "+dev" in suffix:
        return ReleaseChannel.DEV
    if major == 0 or any(marker in suffix for marker in ("a", "b", "rc", "beta", "alpha")):
        return ReleaseChannel.BETA
    return ReleaseChannel.STABLE


def resolve_release_channel(
    requested: str | ReleaseChannel | None = None,
    *,
    version: str = __version__,
    env: Mapping[str, str] | None = None,
) -> ReleaseChannelState:
    values = os.environ if env is None else env
    source = "version-policy"
    raw: str | ReleaseChannel | None = requested
    if raw is None and values.get("AFFILIATE_MATE_CHANNEL", "").strip():
        raw = values["AFFILIATE_MATE_CHANNEL"].strip()
        source = "environment"
    elif raw is not None:
        source = "explicit"

    if raw is None:
        channel = _version_default(version)
    else:
        try:
            channel = raw if isinstance(raw, ReleaseChannel) else ReleaseChannel(raw.strip().lower())
        except ValueError as exc:
            choices = ", ".join(item.value for item in ReleaseChannel)
            raise ReleaseChannelError(f"release channel must be one of: {choices}") from exc

    default = _version_default(version)
    if channel is ReleaseChannel.STABLE and default is not ReleaseChannel.STABLE:
        raise ReleaseChannelError(
            f"version {version} cannot claim the stable channel before stable-version policy is met"
        )
    return ReleaseChannelState(channel=channel, version=version, source=source)
