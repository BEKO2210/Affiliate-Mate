"""High-level deterministic planning helpers for production metadata and adapter stages."""

from __future__ import annotations

from .production_adapters import DryRunTTSAdapter, DryRunThumbnailAdapter, DryRunVideoRenderAdapter
from .production_models import (
    AdapterExecutionPlan,
    DisclosureBundle,
    ScriptDocument,
    ThumbnailBrief,
    VideoMetadata,
)


def build_video_metadata(
    *,
    product_title: str,
    affiliate_url: str,
    disclosure: DisclosureBundle,
    description_body: str = "",
    tags: tuple[str, ...] = (),
) -> VideoMetadata:
    title = product_title.strip()
    if not title:
        raise ValueError("product_title must not be empty")
    if not affiliate_url.strip():
        raise ValueError("affiliate_url must not be empty")
    clean_body = description_body.strip()
    description_parts = [disclosure.description]
    if clean_body:
        description_parts.append(clean_body)
    description_parts.append(f"Product link: {affiliate_url.strip()}")
    return VideoMetadata(
        title=f"{title} — research-based overview",
        description="\n\n".join(description_parts),
        tags=tags,
        affiliate_url=affiliate_url.strip(),
        disclosure=disclosure.description,
    )


def build_thumbnail_brief(
    *,
    product_title: str,
    claim_ids: tuple[str, ...] = (),
) -> ThumbnailBrief:
    title = product_title.strip()
    if not title:
        raise ValueError("product_title must not be empty")
    return ThumbnailBrief(
        headline=title,
        visual_direction=(
            "Clean product-focused thumbnail. Do not add ratings, awards, performance claims, "
            "prices, or comparison badges unless they are explicitly approved research claims."
        ),
        claim_ids=claim_ids,
    )


def build_dry_run_adapter_plans(
    script: ScriptDocument,
    thumbnail: ThumbnailBrief,
) -> tuple[AdapterExecutionPlan, ...]:
    tts = DryRunTTSAdapter().plan(script)
    video = DryRunVideoRenderAdapter().plan(script, narration_plan=tts)
    thumb = DryRunThumbnailAdapter().plan(thumbnail, research_digest=script.research_digest)
    return (tts, video, thumb)
