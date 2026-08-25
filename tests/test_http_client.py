import json

import pytest

from affiliate_mate.http_client import (
    HttpRequestError,
    HttpResponse,
    JsonHttpClient,
    JsonProtocolError,
    RetryPolicy,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def send(self, method, url, *, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        return self.responses.pop(0)


def response(status, data=None, headers=None):
    body = b"" if data is None else json.dumps(data).encode()
    return HttpResponse(status, headers or {}, body)


def test_retries_transient_status_and_respects_retry_after():
    transport = FakeTransport(
        [response(429, {"x": 1}, {"Retry-After": "2"}), response(200, {"ok": True})]
    )
    sleeps = []
    client = JsonHttpClient(transport, sleeper=sleeps.append)
    assert client.request_json("GET", "https://example.invalid") == {"ok": True}
    assert sleeps == [2.0]
    assert len(transport.calls) == 2


def test_exponential_backoff_is_bounded():
    transport = FakeTransport([response(500), response(502), response(200, {"ok": True})])
    sleeps = []
    client = JsonHttpClient(
        transport,
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=1,
            max_delay_seconds=1.5,
        ),
        sleeper=sleeps.append,
    )
    client.request_json("GET", "https://example.invalid")
    assert sleeps == [1, 1.5]


def test_non_retryable_error_fails_immediately():
    transport = FakeTransport([response(400, {"bad": True})])
    client = JsonHttpClient(transport, sleeper=lambda _: None)
    with pytest.raises(HttpRequestError) as exc:
        client.request_json("GET", "https://example.invalid")
    assert exc.value.status == 400
    assert len(transport.calls) == 1


def test_invalid_json_is_protocol_error():
    transport = FakeTransport([HttpResponse(200, {}, b"not-json")])
    with pytest.raises(JsonProtocolError):
        JsonHttpClient(transport).request_json("GET", "https://example.invalid")
