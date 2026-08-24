"""Small dependency-free JSON HTTP client with bounded retry behavior."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> HttpResponse: ...


class UrllibTransport:
    """Production transport implemented only with the Python standard library."""

    def send(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> HttpResponse:
        request = Request(url, data=body, headers=dict(headers), method=method)
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                return HttpResponse(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except HTTPError as exc:
            return HttpResponse(
                status=exc.code,
                headers=dict(exc.headers.items()) if exc.headers else {},
                body=exc.read(),
            )
        except URLError as exc:
            raise TransportError(str(exc.reason)) from exc


class TransportError(RuntimeError):
    pass


class HttpRequestError(RuntimeError):
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self.body = body
        super().__init__(f"HTTP request failed with status {status}")


class JsonProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    retry_statuses: frozenset[int] = field(
        default_factory=lambda: frozenset({408, 425, 429, 500, 502, 503, 504})
    )

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds must be >= 0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")

    def delay_for(self, retry_number: int, headers: Mapping[str, str]) -> float:
        retry_after = _header_value(headers, "retry-after")
        if retry_after is not None:
            try:
                value = float(retry_after)
            except ValueError:
                pass
            else:
                return min(self.max_delay_seconds, max(0.0, value))
        delay = self.base_delay_seconds * (2 ** max(0, retry_number - 1))
        return min(self.max_delay_seconds, delay)


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    lowered = name.casefold()
    for key, value in headers.items():
        if key.casefold() == lowered:
            return value
    return None


class JsonHttpClient:
    """HTTP JSON client with explicit retries and injectable I/O for tests."""

    def __init__(
        self,
        transport: HttpTransport | None = None,
        *,
        retry_policy: RetryPolicy | None = None,
        timeout_seconds: float = 15.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self._transport = transport or UrllibTransport()
        self._retry = retry_policy or RetryPolicy()
        self._timeout = timeout_seconds
        self._sleep = sleeper

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        encoded = None
        request_headers = dict(headers or {})
        if payload is not None:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        last_transport_error: TransportError | None = None
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                response = self._transport.send(
                    method,
                    url,
                    headers=request_headers,
                    body=encoded,
                    timeout=self._timeout,
                )
            except TransportError as exc:
                last_transport_error = exc
                if attempt == self._retry.max_attempts:
                    raise
                self._sleep(self._retry.delay_for(attempt, {}))
                continue

            if 200 <= response.status < 300:
                if not response.body:
                    return {}
                try:
                    decoded = json.loads(response.body)
                except json.JSONDecodeError as exc:
                    raise JsonProtocolError("response was not valid JSON") from exc
                if not isinstance(decoded, dict):
                    raise JsonProtocolError("JSON response root must be an object")
                return decoded

            if response.status not in self._retry.retry_statuses:
                raise HttpRequestError(response.status, response.body)
            if attempt == self._retry.max_attempts:
                raise HttpRequestError(response.status, response.body)
            self._sleep(self._retry.delay_for(attempt, response.headers))

        if last_transport_error is not None:  # pragma: no cover - defensive
            raise last_transport_error
        raise RuntimeError("unreachable retry state")  # pragma: no cover
