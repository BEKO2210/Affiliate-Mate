"""Structured telemetry events with an OpenTelemetry-compatible field boundary."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .learning_models import canonical_json

TELEMETRY_SCHEMA_VERSION = "affiliate-mate.telemetry-event.v1"


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    name: str
    timestamp: datetime
    severity: str = "info"
    trace_id: str | None = None
    span_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("telemetry event name must not be empty")
        _require_aware(self.timestamp)
        if self.severity not in {"debug", "info", "warning", "error", "critical"}:
            raise ValueError("unsupported telemetry severity")
        if self.trace_id is not None and len(self.trace_id) != 32:
            raise ValueError("trace_id must be 32 lowercase hex characters")
        if self.span_id is not None and len(self.span_id) != 16:
            raise ValueError("span_id must be 16 lowercase hex characters")
        for field_name, value in (("trace_id", self.trace_id), ("span_id", self.span_id)):
            if value is not None and any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{field_name} must contain lowercase hexadecimal characters")
        canonical_json(self.attributes)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "name": self.name,
            "timestamp": self.timestamp.astimezone(UTC).isoformat(),
            "severity": self.severity,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "attributes": dict(self.attributes),
        }


@runtime_checkable
class TelemetrySink(Protocol):
    @property
    def name(self) -> str: ...

    def emit(self, event: TelemetryEvent) -> None: ...


@dataclass(slots=True)
class NullTelemetrySink:
    @property
    def name(self) -> str:
        return "null"

    def emit(self, event: TelemetryEvent) -> None:
        del event


@dataclass(slots=True)
class MemoryTelemetrySink:
    events: list[TelemetryEvent] = field(default_factory=list)

    @property
    def name(self) -> str:
        return "memory"

    def emit(self, event: TelemetryEvent) -> None:
        self.events.append(event)


class JsonlTelemetrySink:
    """Append one strict JSON event per line without buffering secrets in global logging state."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "jsonl"

    def emit(self, event: TelemetryEvent) -> None:
        payload = (
            json.dumps(
                event.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        with self._lock:
            fd = os.open(self.path, flags, 0o600)
            try:
                os.write(fd, payload)
                os.fsync(fd)
            finally:
                os.close(fd)
        os.chmod(self.path, 0o600)


def event_from_exception(
    name: str,
    exc: BaseException,
    *,
    at: datetime,
    attributes: dict[str, Any] | None = None,
    safe_message: str | None = None,
) -> TelemetryEvent:
    """Create an error event without serializing traceback locals or raw exception messages.

    Exception messages frequently embed provider payloads, tokens, file paths, or user data. Only
    the exception type is recorded automatically. A caller may add an explicitly reviewed
    `safe_message`; arbitrary `str(exc)` is intentionally not emitted.
    """

    safe_attributes = dict(attributes or {})
    safe_attributes["exception_type"] = type(exc).__name__
    if safe_message is not None:
        if not safe_message.strip():
            raise ValueError("safe_message must not be blank")
        safe_attributes["safe_message"] = safe_message
    return TelemetryEvent(
        name=name,
        timestamp=at,
        severity="error",
        attributes=safe_attributes,
    )
