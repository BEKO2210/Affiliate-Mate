import json

import pytest

from affiliate_mate.amazon_creators import (
    AmazonCreatorsClient,
    AmazonCreatorsCredentials,
    AmazonCreatorsError,
    AmazonCreatorsProtocolError,
    marketplace_spec,
)
from affiliate_mate.http_client import HttpRequestError


class ScriptedJsonClient:
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []

    def request_json(self, method, url, *, headers=None, payload=None):
        self.calls.append((method, url, headers or {}, payload))
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def credentials(version="3.2"):
    return AmazonCreatorsCredentials("credential", "secret", "tag-21", version)


def search_response(currency="EUR"):
    return {
        "searchResult": {
            "items": [
                {
                    "asin": "B012345678",
                    "detailPageURL": "https://www.amazon.de/dp/B012345678?tag=tag-21",
                    "itemInfo": {
                        "title": {"displayValue": "Test Camera"},
                        "byLineInfo": {"brand": {"displayValue": "TestBrand"}},
                    },
                    "browseNodeInfo": {
                        "browseNodes": [{"contextFreeName": "Electronics"}]
                    },
                    "offersV2": {
                        "listings": [
                            {
                                "price": {
                                    "money": {
                                        "amount": 199.99,
                                        "currency": currency,
                                    }
                                }
                            }
                        ]
                    },
                }
            ]
        }
    }


def test_marketplace_mapping_and_credential_endpoint():
    assert marketplace_spec("de").domain == "www.amazon.de"
    assert marketplace_spec("DE").currency == "EUR"
    assert credentials().token_endpoint == "https://api.amazon.co.uk/auth/o2/token"
    with pytest.raises(ValueError, match="unsupported"):
        marketplace_spec("XX")


def test_credentials_from_env_requires_every_secret():
    with pytest.raises(ValueError, match="AMAZON_ASSOCIATE_TAG"):
        AmazonCreatorsCredentials.from_env(
            {
                "AMAZON_CREATORS_CREDENTIAL_ID": "id",
                "AMAZON_CREATORS_CREDENTIAL_SECRET": "secret",
                "AMAZON_CREATORS_CREDENTIAL_VERSION": "3.2",
            }
        )


def test_token_is_cached_and_search_payload_matches_creators_api_contract():
    clock = iter([100.0, 100.0, 120.0])
    http = ScriptedJsonClient(
        [
            {"access_token": "token", "expires_in": 3600},
            search_response(),
            search_response(),
        ]
    )
    client = AmazonCreatorsClient(credentials(), http=http, monotonic=lambda: next(clock))
    first = client.search_items(
        "camera",
        marketplace="DE",
        limit=5,
        search_index="Electronics",
    )
    second = client.search_items(
        "camera",
        marketplace="DE",
        limit=5,
        search_index="Electronics",
    )
    assert first[0].price == 199.99
    assert first[0].category == "Electronics"
    assert first[0].brand == "TestBrand"
    assert second[0].currency == "EUR"
    assert len([call for call in http.calls if call[1].endswith("/auth/o2/token")]) == 1
    search_call = next(call for call in http.calls if call[1].endswith("/searchItems"))
    assert search_call[2]["x-marketplace"] == "www.amazon.de"
    assert search_call[2]["Authorization"] == "Bearer token"
    assert search_call[3]["partnerTag"] == "tag-21"
    assert search_call[3]["itemCount"] == 5
    assert search_call[3]["searchIndex"] == "Electronics"
    assert search_call[3]["marketplace"] == "www.amazon.de"


def test_unauthorized_catalog_call_refreshes_token_once():
    unauthorized = HttpRequestError(
        401,
        json.dumps({"code": "Unauthorized", "message": "expired"}).encode(),
    )
    clock = iter([100.0, 100.0, 100.0, 100.0])
    http = ScriptedJsonClient(
        [
            {"access_token": "old", "expires_in": 3600},
            unauthorized,
            {"access_token": "new", "expires_in": 3600},
            search_response(),
        ]
    )
    client = AmazonCreatorsClient(credentials(), http=http, monotonic=lambda: next(clock))
    assert client.search_items("camera", marketplace="DE")[0].product_id == "B012345678"
    auth_headers = [
        call[2]["Authorization"]
        for call in http.calls
        if call[1].endswith("/searchItems")
    ]
    assert auth_headers == ["Bearer old", "Bearer new"]


def test_currency_mismatch_fails_closed():
    http = ScriptedJsonClient(
        [{"access_token": "token", "expires_in": 3600}, search_response("USD")]
    )
    client = AmazonCreatorsClient(credentials(), http=http, monotonic=lambda: 100.0)
    with pytest.raises(AmazonCreatorsProtocolError, match="expected EUR"):
        client.search_items("camera", marketplace="DE")


def test_search_and_get_items_enforce_api_batch_limits():
    client = AmazonCreatorsClient(credentials(), http=ScriptedJsonClient([]))
    with pytest.raises(ValueError, match="between 1 and 10"):
        client.search_items("camera", marketplace="DE", limit=11)
    with pytest.raises(ValueError, match="at most 10"):
        client.get_items([str(i) for i in range(11)], marketplace="DE")


def test_amazon_error_is_structured_without_leaking_credentials():
    failure = HttpRequestError(
        403,
        json.dumps(
            {"errors": [{"code": "AccessDenied", "message": "not allowed"}]}
        ).encode(),
    )
    http = ScriptedJsonClient([failure])
    client = AmazonCreatorsClient(credentials(), http=http, monotonic=lambda: 100.0)
    with pytest.raises(AmazonCreatorsError) as exc:
        client.search_items("camera", marketplace="DE")
    assert exc.value.status == 403
    assert exc.value.code == "AccessDenied"
    assert "secret" not in str(exc.value)
