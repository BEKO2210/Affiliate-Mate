"""Strict importers for user-owned video and affiliate outcome exports."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from .learning_models import OutcomeEvent, OutcomeKind


class OutcomeImportError(ValueError):
    """Raised when an outcome export is ambiguous or invalid."""


def _parse_time(raw: str, field_name: str) -> datetime:
    value = raw.strip()
    if not value:
        raise OutcomeImportError(f"{field_name} must not be empty")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise OutcomeImportError(f"{field_name} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OutcomeImportError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _nonnegative_int(raw: str, field_name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise OutcomeImportError(f"{field_name} must be an integer") from exc
    if value < 0:
        raise OutcomeImportError(f"{field_name} must be >= 0")
    return value


def _require_columns(fieldnames: Iterable[str] | None, required: set[str]) -> None:
    available = set(fieldnames or ())
    missing = sorted(required - available)
    if missing:
        raise OutcomeImportError(f"missing required columns: {', '.join(missing)}")


def _common_row(
    row: dict[str, str],
    *,
    ingested_at: datetime,
) -> dict[str, object]:
    product_id = row["product_id"].strip()
    marketplace = row["marketplace"].strip().upper()
    content_id = row["content_id"].strip()
    source_event_id = row["source_event_id"].strip()
    if not all((product_id, marketplace, content_id, source_event_id)):
        raise OutcomeImportError(
            "source_event_id, product_id, marketplace, and content_id must not be empty"
        )
    window_start = _parse_time(row["window_start"], "window_start")
    window_end = _parse_time(row["window_end"], "window_end")
    observed_at = _parse_time(row["observed_at"], "observed_at")
    effective_raw = row.get("effective_at", "").strip()
    effective_at = (
        window_end
        if not effective_raw
        else _parse_time(effective_raw, "effective_at")
    )
    package_digest = row.get("package_digest", "").strip() or None
    return {
        "source_event_id": source_event_id,
        "product_id": product_id,
        "marketplace": marketplace,
        "content_id": content_id,
        "package_digest": package_digest,
        "effective_at": effective_at,
        "observed_at": observed_at,
        "ingested_at": ingested_at,
        "window_start": window_start,
        "window_end": window_end,
    }


def load_video_analytics_csv(
    path: str | Path,
    *,
    ingested_at: datetime,
    source: str = "youtube-export",
) -> list[OutcomeEvent]:
    """Import explicit view snapshots.

    Rows must carry product/content lineage. Titles are deliberately ignored as join keys.
    """

    if ingested_at.tzinfo is None or ingested_at.utcoffset() is None:
        raise ValueError("ingested_at must be timezone-aware")
    required = {
        "source_event_id",
        "product_id",
        "marketplace",
        "content_id",
        "window_start",
        "window_end",
        "observed_at",
        "views",
    }
    events: list[OutcomeEvent] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames, required)
        for line_number, row in enumerate(reader, start=2):
            try:
                common = _common_row(row, ingested_at=ingested_at)
                events.append(
                    OutcomeEvent(
                        source=source,
                        kind=OutcomeKind.VIDEO_VIEW,
                        count=_nonnegative_int(row["views"], "views"),
                        metadata={"import_line": line_number},
                        **common,
                    )
                )
            except (KeyError, ValueError) as exc:
                raise OutcomeImportError(f"{path}:{line_number}: {exc}") from exc
    return events


def load_affiliate_outcomes_csv(
    path: str | Path,
    *,
    ingested_at: datetime,
    source: str = "affiliate-export",
) -> list[OutcomeEvent]:
    """Import clicks, orders, commission, refunds, and reversals from one explicit row."""

    if ingested_at.tzinfo is None or ingested_at.utcoffset() is None:
        raise ValueError("ingested_at must be timezone-aware")
    required = {
        "source_event_id",
        "product_id",
        "marketplace",
        "content_id",
        "window_start",
        "window_end",
        "observed_at",
        "clicks",
        "orders",
        "commission_minor",
        "refund_minor",
        "reversal_minor",
        "currency",
    }
    events: list[OutcomeEvent] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_columns(reader.fieldnames, required)
        for line_number, row in enumerate(reader, start=2):
            try:
                common = _common_row(row, ingested_at=ingested_at)
                currency = row["currency"].strip().upper()
                if len(currency) != 3:
                    raise OutcomeImportError("currency must be a three-letter code")
                metadata = {"import_line": line_number}
                events.extend(
                    (
                        OutcomeEvent(
                            source=source,
                            kind=OutcomeKind.AFFILIATE_CLICK,
                            count=_nonnegative_int(row["clicks"], "clicks"),
                            metadata=metadata,
                            **common,
                        ),
                        OutcomeEvent(
                            source=source,
                            kind=OutcomeKind.ORDER,
                            count=_nonnegative_int(row["orders"], "orders"),
                            metadata=metadata,
                            **common,
                        ),
                        OutcomeEvent(
                            source=source,
                            kind=OutcomeKind.COMMISSION,
                            amount_minor=_nonnegative_int(
                                row["commission_minor"],
                                "commission_minor",
                            ),
                            currency=currency,
                            metadata=metadata,
                            **common,
                        ),
                        OutcomeEvent(
                            source=source,
                            kind=OutcomeKind.REFUND,
                            amount_minor=_nonnegative_int(row["refund_minor"], "refund_minor"),
                            currency=currency,
                            metadata=metadata,
                            **common,
                        ),
                        OutcomeEvent(
                            source=source,
                            kind=OutcomeKind.REVERSAL,
                            amount_minor=_nonnegative_int(
                                row["reversal_minor"],
                                "reversal_minor",
                            ),
                            currency=currency,
                            metadata=metadata,
                            **common,
                        ),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise OutcomeImportError(f"{path}:{line_number}: {exc}") from exc
    return events
