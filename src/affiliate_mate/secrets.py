"""Provider-neutral secret retrieval without persisting secret values in project state."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class SecretNotFoundError(KeyError):
    """Raised when a required secret is not available from a provider."""


@runtime_checkable
class SecretsProvider(Protocol):
    @property
    def name(self) -> str: ...

    def get(self, key: str) -> str | None: ...


def require_secret(provider: SecretsProvider, key: str) -> str:
    normalized = key.strip()
    if not normalized:
        raise ValueError("secret key must not be empty")
    value = provider.get(normalized)
    if value is None or not value:
        raise SecretNotFoundError(
            f"required secret {normalized!r} is unavailable from provider {provider.name!r}"
        )
    return value


@dataclass(frozen=True, slots=True)
class EnvSecretsProvider:
    prefix: str = ""

    @property
    def name(self) -> str:
        return "environment"

    def get(self, key: str) -> str | None:
        normalized = key.strip()
        if not normalized:
            raise ValueError("secret key must not be empty")
        return os.environ.get(f"{self.prefix}{normalized}")


@dataclass(frozen=True, slots=True)
class MappingSecretsProvider:
    """Deterministic test/development provider whose values are hidden from repr()."""

    values: Mapping[str, str] = field(repr=False)
    provider_name: str = "mapping"

    @property
    def name(self) -> str:
        return self.provider_name

    def get(self, key: str) -> str | None:
        normalized = key.strip()
        if not normalized:
            raise ValueError("secret key must not be empty")
        return self.values.get(normalized)


@dataclass(frozen=True, slots=True)
class ChainedSecretsProvider:
    providers: tuple[SecretsProvider, ...]

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError("at least one secrets provider is required")

    @property
    def name(self) -> str:
        return "chain[" + ",".join(provider.name for provider in self.providers) + "]"

    def get(self, key: str) -> str | None:
        for provider in self.providers:
            value = provider.get(key)
            if value is not None:
                return value
        return None
