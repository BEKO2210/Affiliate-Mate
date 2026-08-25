"""Provider-neutral production adapter contracts and deterministic dry-run implementations."""

from __future__ import annotations

from typing import Protocol

from .production_models import (
    AdapterExecutionPlan,
    ScriptDocument,
    ThumbnailBrief,
    VideoMetadata,
    canonical_json,
    sha256_text,
)


class TTSAdapter(Protocol):
    name: str

    def plan(self, script: ScriptDocument) -> AdapterExecutionPlan:
        """Return an auditable plan before any synthesis side effect."""


class VideoRenderAdapter(Protocol):
    name: str

    def plan(
        self,
        script: ScriptDocument,
        *,
        narration_plan: AdapterExecutionPlan,
    ) -> AdapterExecutionPlan:
        """Return an auditable video render plan."""


class ThumbnailAdapter(Protocol):
    name: str

    def plan(self, brief: ThumbnailBrief, *, research_digest: str) -> AdapterExecutionPlan:
        """Return an auditable thumbnail-generation plan."""


class PublisherAdapter(Protocol):
    name: str

    def plan(
        self,
        metadata: VideoMetadata,
        *,
        package_digest: str,
    ) -> AdapterExecutionPlan:
        """Return a publish plan; live implementations must still enforce production gates."""


class DryRunTTSAdapter:
    name = "dry-run-tts-v1"

    def plan(self, script: ScriptDocument) -> AdapterExecutionPlan:
        return AdapterExecutionPlan(
            adapter=self.name,
            action="synthesize-narration",
            input_digest=script.digest,
            side_effecting=False,
            parameters={
                "language": script.language,
                "characters": len(script.narration_text),
            },
        )


class DryRunVideoRenderAdapter:
    name = "dry-run-video-v1"

    def plan(
        self,
        script: ScriptDocument,
        *,
        narration_plan: AdapterExecutionPlan,
    ) -> AdapterExecutionPlan:
        payload = {
            "script_digest": script.digest,
            "narration_plan": narration_plan.to_dict(),
            "resolution": "1920x1080",
            "aspect_ratio": "16:9",
        }
        return AdapterExecutionPlan(
            adapter=self.name,
            action="render-video",
            input_digest=sha256_text(canonical_json(payload)),
            side_effecting=False,
            parameters={
                "resolution": "1920x1080",
                "aspect_ratio": "16:9",
            },
        )


class DryRunThumbnailAdapter:
    name = "dry-run-thumbnail-v1"

    def plan(self, brief: ThumbnailBrief, *, research_digest: str) -> AdapterExecutionPlan:
        payload = {
            "brief": brief.to_dict(),
            "research_digest": research_digest,
        }
        return AdapterExecutionPlan(
            adapter=self.name,
            action="render-thumbnail",
            input_digest=sha256_text(canonical_json(payload)),
            side_effecting=False,
            parameters={"resolution": "1280x720"},
        )


class DryRunYouTubePublisher:
    name = "dry-run-youtube-v1"

    def plan(
        self,
        metadata: VideoMetadata,
        *,
        package_digest: str,
    ) -> AdapterExecutionPlan:
        payload = {
            "metadata": metadata.to_dict(),
            "package_digest": package_digest,
        }
        return AdapterExecutionPlan(
            adapter=self.name,
            action="youtube-upload",
            input_digest=sha256_text(canonical_json(payload)),
            side_effecting=False,
            parameters={"privacy_status": "private", "dry_run": True},
        )
