import json
import os
from datetime import UTC, datetime

import pytest

from affiliate_mate.observability import (
    JsonlTelemetrySink,
    MemoryTelemetrySink,
    TelemetryEvent,
    event_from_exception,
)


def now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def test_memory_sink_preserves_structured_event() -> None:
    event = TelemetryEvent(
        name="job.completed",
        timestamp=now(),
        trace_id="a" * 32,
        span_id="b" * 16,
        attributes={"job_key": "render:1", "attempt": 1},
    )
    sink = MemoryTelemetrySink()
    sink.emit(event)
    assert sink.events == [event]
    assert event.to_dict()["schema_version"] == "affiliate-mate.telemetry-event.v1"


def test_jsonl_sink_appends_strict_json_and_private_permissions(tmp_path) -> None:
    path = tmp_path / "logs" / "ops.jsonl"
    sink = JsonlTelemetrySink(path)
    sink.emit(TelemetryEvent(name="one", timestamp=now(), attributes={"n": 1}))
    sink.emit(TelemetryEvent(name="two", timestamp=now(), attributes={"n": 2}))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["name"] for row in rows] == ["one", "two"]
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_exception_event_does_not_emit_raw_exception_message() -> None:
    secret = "TOKEN-super-secret"
    event = event_from_exception(
        "provider.failed",
        RuntimeError(f"upstream failed with {secret}"),
        at=now(),
    )
    serialized = json.dumps(event.to_dict())
    assert secret not in serialized
    assert event.attributes == {"exception_type": "RuntimeError"}


def test_safe_exception_message_is_explicit() -> None:
    event = event_from_exception(
        "provider.failed",
        RuntimeError("sensitive details"),
        at=now(),
        safe_message="provider request failed",
    )
    assert event.attributes["safe_message"] == "provider request failed"


def test_invalid_trace_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="trace_id"):
        TelemetryEvent(name="bad", timestamp=now(), trace_id="z" * 32)
