"""Amazon Creators API catalog adapter with OAuth token caching and fail-closed parsing."""

import json
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Self

from .catalog import CatalogItem
from .http_client import HttpRequestError, JsonHttpClient

CREATORS_API_BASE_URL = "https://creatorsapi.amazon/catalog/v1"
TOKEN_SCOPE = "creatorsapi::default"
TOKEN_ENDPOINTS = {
    "3.1": "https://api.amazon.com/auth/o2/token",
    "3.2": "https://api.amazon.co.uk/auth/o2/token",
    "3.3": "https://api.amazon.co.jp/auth/o2/token",
}


@dataclass(frozen=True, slots=True)
class AmazonMarketplace:
    code: str
    domain: str
    currency: str


_MARKETPLACES = {
    "AU": AmazonMarketplace("AU", "www.amazon.com.au", "AUD"),
    "BE": AmazonMarketplace("BE", "www.amazon.com.be", "EUR"),
    "BR": AmazonMarketplace("BR", "www.amazon.com.br", "BRL"),
    "CA": AmazonMarketplace("CA", "www.amazon.ca", "CAD"),
    "DE": AmazonMarketplace("DE", "www.amazon.de", "EUR"),
    "EG": AmazonMarketplace("EG", "www.amazon.eg", "EGP"),
    "ES": AmazonMarketplace("ES", "www.amazon.es", "EUR"),
    "FR": AmazonMarketplace("FR", "www.amazon.fr", "EUR"),
    "IE": AmazonMarketplace("IE", "www.amazon.ie", "EUR"),
    "IN": AmazonMarketplace("IN", "www.amazon.in", "INR"),
    "IT": AmazonMarketplace("IT", "www.amazon.it", "EUR"),
    "JP": AmazonMarketplace("JP", "www.amazon.co.jp", "JPY"),
    "MX": AmazonMarketplace("MX", "www.amazon.com.mx", "MXN"),
    "NL": AmazonMarketplace("NL", "www.amazon.nl", "EUR"),
    "PL": AmazonMarketplace("PL", "www.amazon.pl", "PLN"),
    "SA": AmazonMarketplace("SA", "www.amazon.sa", "SAR"),
    "SE": AmazonMarketplace("SE", "www.amazon.se", "SEK"),
    "SG": AmazonMarketplace("SG", "www.amazon.sg", "SGD"),
    "TR": AmazonMarketplace("TR", "www.amazon.com.tr", "TRY"),
    "AE": AmazonMarketplace("AE", "www.amazon.ae", "AED"),
    "UK": AmazonMarketplace("UK", "www.amazon.co.uk", "GBP"),
    "US": AmazonMarketplace("US", "www.amazon.com", "USD"),
}

DEFAULT_RESOURCES = (
    "itemInfo.title",
    "itemInfo.byLineInfo",
    "offersV2.listings.price",
    "browseNodeInfo.browseNodes",
)


@dataclass(frozen=True, slots=True)
class AmazonCreatorsCredentials:
    credential_id: str = field(repr=False)
    credential_secret: str = field(repr=False)
    partner_tag: str
    version: str

    def __post_init__(self) -> None:
        if not self.credential_id.strip():
            raise ValueError("credential_id must not be empty")
        if not self.credential_secret.strip():
            raise ValueError("credential_secret must not be empty")
        if not self.partner_tag.strip():
            raise ValueError("partner_tag must not be empty")
        if self.version not in TOKEN_ENDPOINTS:
            raise ValueError(f"unsupported Creators API credential version: {self.version!r}")

    @property
    def token_endpoint(self) -> str:
        return TOKEN_ENDPOINTS[self.version]

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        values = os.environ if env is None else env
        names = {
            "credential_id": "AMAZON_CREATORS_CREDENTIAL_ID",
            "credential_secret": "AMAZON_CREATORS_CREDENTIAL_SECRET",
            "partner_tag": "AMAZON_ASSOCIATE_TAG",
            "version": "AMAZON_CREATORS_CREDENTIAL_VERSION",
        }
        missing = [name for name in names.values() if not values.get(name, "").strip()]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"missing required Amazon environment variables: {joined}")
        return cls(**{key: values[name] for key, name in names.items()})


@dataclass(frozen=True, slots=True)
class _CachedToken:
    value: str = field(repr=False)
    expires_at_monotonic: float


class AmazonCreatorsError(RuntimeError):
    def __init__(self, status: int, code: str | None, message: str | None) -> None:
        self.status = status
        self.code = code
        self.api_message = message
        detail = ": ".join(part for part in (code, message) if part) or "unknown API error"
        super().__init__(f"Amazon Creators API error ({status}): {detail}")


class AmazonCreatorsProtocolError(RuntimeError):
    pass


class AmazonCreatorsClient:
    """Low-level Creators API client with injectable HTTP and time sources."""

    def __init__(
        self,
        credentials: AmazonCreatorsCredentials,
        *,
        http: JsonHttpClient | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        token_expiry_skew_seconds: float = 30.0,
    ) -> None:
        if token_expiry_skew_seconds < 0:
            raise ValueError("token_expiry_skew_seconds must be >= 0")
        self._credentials = credentials
        self._http = http or JsonHttpClient()
        self._monotonic = monotonic
        self._token_expiry_skew = token_expiry_skew_seconds
        self._token: _CachedToken | None = None
        self._token_lock = threading.Lock()

    @property
    def name(self) -> str:
        return "amazon-creators-api"

    def search_items(
        self,
        keywords: str,
        *,
        marketplace: str,
        limit: int = 10,
        search_index: str = "All",
        resources: tuple[str, ...] = DEFAULT_RESOURCES,
    ) -> list[CatalogItem]:
        if not keywords.strip():
            raise ValueError("keywords must not be empty")
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        if not search_index.strip():
            raise ValueError("search_index must not be empty")
        spec = marketplace_spec(marketplace)
        payload = {
            "partnerTag": self._credentials.partner_tag,
            "marketplace": spec.domain,
            "keywords": keywords,
            "searchIndex": search_index,
            "itemCount": limit,
            "resources": list(resources),
        }
        data = self._catalog_request("searchItems", spec, payload)
        return _items_from_result(data, "searchResult", spec)

    def get_items(
        self,
        item_ids: list[str] | tuple[str, ...],
        *,
        marketplace: str,
        resources: tuple[str, ...] = DEFAULT_RESOURCES,
    ) -> list[CatalogItem]:
        ids = [item_id.strip() for item_id in item_ids]
        if not ids or any(not item_id for item_id in ids):
            raise ValueError("item_ids must contain at least one non-empty ASIN")
        if len(ids) > 10:
            raise ValueError("get_items accepts at most 10 ASINs per request")
        spec = marketplace_spec(marketplace)
        payload = {
            "partnerTag": self._credentials.partner_tag,
            "marketplace": spec.domain,
            "itemIds": ids,
            "itemIdType": "ASIN",
            "resources": list(resources),
        }
        data = self._catalog_request("getItems", spec, payload)
        return _items_from_result(data, "itemsResult", spec)

    def _catalog_request(
        self,
        operation: str,
        marketplace: AmazonMarketplace,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        try:
            return self._post_catalog(operation, marketplace, payload, self._access_token())
        except AmazonCreatorsError as exc:
            if exc.status != 401:
                raise
        self._invalidate_token()
        return self._post_catalog(operation, marketplace, payload, self._access_token())

    def _post_catalog(
        self,
        operation: str,
        marketplace: AmazonMarketplace,
        payload: Mapping[str, object],
        token: str,
    ) -> dict[str, object]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-marketplace": marketplace.domain,
        }
        try:
            return self._http.request_json(
                "POST",
                f"{CREATORS_API_BASE_URL}/{operation}",
                headers=headers,
                payload=payload,
            )
        except HttpRequestError as exc:
            raise _decode_amazon_error(exc) from exc

    def _access_token(self) -> str:
        now = float(self._monotonic())
        cached = self._token
        if cached is not None and now < cached.expires_at_monotonic:
            return cached.value
        with self._token_lock:
            now = float(self._monotonic())
            cached = self._token
            if cached is not None and now < cached.expires_at_monotonic:
                return cached.value
            token = self._fetch_token(now)
            self._token = token
            return token.value

    def _fetch_token(self, now: float) -> _CachedToken:
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._credentials.credential_id,
            "client_secret": self._credentials.credential_secret,
            "scope": TOKEN_SCOPE,
        }
        try:
            response = self._http.request_json(
                "POST",
                self._credentials.token_endpoint,
                headers={"Content-Type": "application/json"},
                payload=payload,
            )
        except HttpRequestError as exc:
            raise _decode_amazon_error(exc) from exc
        access_token = response.get("access_token")
        expires_in = response.get("expires_in")
        if not isinstance(access_token, str) or not access_token:
            raise AmazonCreatorsProtocolError("token response missing access_token")
        if not isinstance(expires_in, (int, float)) or expires_in <= 0:
            raise AmazonCreatorsProtocolError("token response missing positive expires_in")
        ttl = max(0.0, float(expires_in) - self._token_expiry_skew)
        return _CachedToken(access_token, now + ttl)

    def _invalidate_token(self) -> None:
        with self._token_lock:
            self._token = None


class AmazonCatalogProvider:
    """High-level search provider backed by Amazon Creators API."""

    def __init__(self, client: AmazonCreatorsClient, *, search_index: str = "All") -> None:
        self._client = client
        self._search_index = search_index

    @property
    def name(self) -> str:
        return self._client.name

    def search(
        self,
        keywords: str,
        *,
        marketplace: str,
        limit: int = 10,
    ) -> list[CatalogItem]:
        return self._client.search_items(
            keywords,
            marketplace=marketplace,
            limit=limit,
            search_index=self._search_index,
        )


def marketplace_spec(code: str) -> AmazonMarketplace:
    normalized = code.strip().upper()
    try:
        return _MARKETPLACES[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(_MARKETPLACES))
        raise ValueError(
            f"unsupported Amazon marketplace {code!r}; supported: {supported}"
        ) from exc


def _items_from_result(
    data: Mapping[str, object],
    result_key: str,
    marketplace: AmazonMarketplace,
) -> list[CatalogItem]:
    result = data.get(result_key)
    if not isinstance(result, dict):
        raise AmazonCreatorsProtocolError(f"response missing {result_key} object")
    items = result.get("items", [])
    if not isinstance(items, list):
        raise AmazonCreatorsProtocolError(f"{result_key}.items must be an array")
    return [_parse_catalog_item(item, marketplace) for item in items]


def _parse_catalog_item(raw: object, marketplace: AmazonMarketplace) -> CatalogItem:
    if not isinstance(raw, dict):
        raise AmazonCreatorsProtocolError("catalog item must be an object")
    asin = raw.get("asin")
    if not isinstance(asin, str) or not asin:
        raise AmazonCreatorsProtocolError("catalog item missing asin")
    title = _nested(raw, "itemInfo", "title", "displayValue")
    if not isinstance(title, str) or not title.strip():
        raise AmazonCreatorsProtocolError(f"catalog item {asin} missing title")

    amount, currency = _extract_price(raw)
    if currency is not None and currency != marketplace.currency:
        raise AmazonCreatorsProtocolError(
            f"catalog item {asin} returned {currency}, expected {marketplace.currency} "
            f"for marketplace {marketplace.code}"
        )

    brand = _nested(raw, "itemInfo", "byLineInfo", "brand", "displayValue")
    detail_url = raw.get("detailPageURL")
    return CatalogItem(
        provider="amazon-creators-api",
        product_id=asin,
        title=title.strip(),
        marketplace=marketplace.code,
        price=amount,
        currency=currency,
        detail_url=detail_url if isinstance(detail_url, str) else None,
        category=_extract_category(raw),
        brand=brand if isinstance(brand, str) else None,
    )


def _extract_price(raw: Mapping[str, object]) -> tuple[float | None, str | None]:
    listings = _nested(raw, "offersV2", "listings")
    if not isinstance(listings, list):
        return None, None
    for listing in listings:
        money = _nested(listing, "price", "money")
        if not isinstance(money, dict):
            continue
        amount = money.get("amount")
        currency = money.get("currency")
        if isinstance(amount, (int, float)) and isinstance(currency, str):
            return float(amount), currency.upper()
    return None, None


def _extract_category(raw: Mapping[str, object]) -> str | None:
    browse_nodes = _nested(raw, "browseNodeInfo", "browseNodes")
    if not isinstance(browse_nodes, list) or not browse_nodes:
        return None
    first = browse_nodes[0]
    if not isinstance(first, dict):
        return None
    for key in ("contextFreeName", "displayName"):
        value = first.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _nested(value: object, *path: str) -> object:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _decode_amazon_error(exc: HttpRequestError) -> AmazonCreatorsError:
    try:
        data = json.loads(exc.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        data = None
    code = None
    message = None
    if isinstance(data, dict):
        code, message = _extract_error_fields(data)
    return AmazonCreatorsError(exc.status, code, message)


def _extract_error_fields(data: Mapping[str, object]) -> tuple[str | None, str | None]:
    errors = data.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        first = errors[0]
        code = first.get("code") or first.get("Code")
        message = first.get("message") or first.get("Message")
        return _as_optional_str(code), _as_optional_str(message)
    code = data.get("code") or data.get("Code")
    message = data.get("message") or data.get("Message")
    return _as_optional_str(code), _as_optional_str(message)


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
