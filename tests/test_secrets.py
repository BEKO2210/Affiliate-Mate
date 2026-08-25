import pytest

from affiliate_mate.secrets import (
    ChainedSecretsProvider,
    MappingSecretsProvider,
    SecretNotFoundError,
    require_secret,
)


def test_mapping_provider_hides_values_from_repr() -> None:
    secret = "super-secret-value"
    provider = MappingSecretsProvider({"API_TOKEN": secret})
    assert secret not in repr(provider)
    assert require_secret(provider, "API_TOKEN") == secret


def test_chained_provider_uses_first_available_value() -> None:
    provider = ChainedSecretsProvider(
        (
            MappingSecretsProvider({}, provider_name="empty"),
            MappingSecretsProvider({"KEY": "second"}, provider_name="second"),
            MappingSecretsProvider({"KEY": "third"}, provider_name="third"),
        )
    )
    assert require_secret(provider, "KEY") == "second"


def test_missing_secret_error_does_not_include_other_values() -> None:
    provider = MappingSecretsProvider({"OTHER": "should-never-leak"})
    with pytest.raises(SecretNotFoundError) as captured:
        require_secret(provider, "MISSING")
    assert "should-never-leak" not in str(captured.value)


def test_blank_secret_key_is_rejected() -> None:
    provider = MappingSecretsProvider({})
    with pytest.raises(ValueError, match="must not be empty"):
        require_secret(provider, "   ")
