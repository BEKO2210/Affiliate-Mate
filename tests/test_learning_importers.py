from datetime import UTC, datetime

import pytest

from affiliate_mate.learning_importers import (
    OutcomeImportError,
    load_affiliate_outcomes_csv,
    load_video_analytics_csv,
)
from affiliate_mate.learning_models import OutcomeKind


def test_video_import_preserves_explicit_lineage_and_zero_views(tmp_path) -> None:
    source = tmp_path / "video.csv"
    source.write_text(
        "source_event_id,product_id,marketplace,content_id,window_start,window_end,"
        "observed_at,views,package_digest\n"
        "yt-1,p1,DE,video-1,2026-01-01T00:00:00Z,2026-01-02T00:00:00Z,"
        "2026-01-03T00:00:00Z,0,\n",
        encoding="utf-8",
    )
    events = load_video_analytics_csv(
        source,
        ingested_at=datetime(2026, 1, 4, tzinfo=UTC),
    )
    assert len(events) == 1
    assert events[0].kind is OutcomeKind.VIDEO_VIEW
    assert events[0].count == 0
    assert events[0].content_id == "video-1"


def test_affiliate_import_expands_one_report_row_into_explicit_metrics(tmp_path) -> None:
    source = tmp_path / "affiliate.csv"
    source.write_text(
        "source_event_id,product_id,marketplace,content_id,window_start,window_end,"
        "observed_at,clicks,orders,commission_minor,refund_minor,reversal_minor,currency\n"
        "aff-1,p1,DE,video-1,2026-01-01T00:00:00Z,2026-01-02T00:00:00Z,"
        "2026-01-05T00:00:00Z,25,2,1200,300,100,EUR\n",
        encoding="utf-8",
    )
    events = load_affiliate_outcomes_csv(
        source,
        ingested_at=datetime(2026, 1, 6, tzinfo=UTC),
    )
    assert [event.kind for event in events] == [
        OutcomeKind.AFFILIATE_CLICK,
        OutcomeKind.ORDER,
        OutcomeKind.COMMISSION,
        OutcomeKind.REFUND,
        OutcomeKind.REVERSAL,
    ]
    assert sum(event.signed_amount_minor for event in events) == 800


def test_import_rejects_naive_source_timestamp(tmp_path) -> None:
    source = tmp_path / "video.csv"
    source.write_text(
        "source_event_id,product_id,marketplace,content_id,window_start,window_end,"
        "observed_at,views\n"
        "yt-1,p1,DE,video-1,2026-01-01T00:00:00Z,2026-01-02T00:00:00Z,"
        "2026-01-03T00:00:00,10\n",
        encoding="utf-8",
    )
    with pytest.raises(OutcomeImportError, match="timezone"):
        load_video_analytics_csv(
            source,
            ingested_at=datetime(2026, 1, 4, tzinfo=UTC),
        )
