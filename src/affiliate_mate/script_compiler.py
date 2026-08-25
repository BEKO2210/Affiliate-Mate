"""LLM-neutral script request construction and deterministic safe baseline generation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from .production_models import (
    DisclosureBundle,
    GroundedClaim,
    ProductionAuthorization,
    ScriptDocument,
    ScriptRequest,
    ScriptSegment,
    ScriptSegmentKind,
)
from .production_policy import assert_authorization_current, validate_script_grounding
from .research_models import ClaimState, EvidenceStance
from .research_store import ResearchWorkspaceStore

DEFAULT_SCRIPT_CONSTRAINTS = (
    "Do not claim first-hand product use unless that experience exists as an approved claim.",
    "Every factual product statement must reference one or more supplied claim IDs.",
    "Do not add specifications, rankings, prices, guarantees, or comparisons not in the claims.",
    "Preserve material caveats and never hide contradictory evidence.",
    "Keep the affiliate disclosure explicit and separate from product claims.",
)


class ScriptGenerator(Protocol):
    name: str

    def generate(
        self,
        request: ScriptRequest,
        *,
        created_at: datetime | None = None,
    ) -> ScriptDocument:
        """Generate a structured script from an explicitly grounded request."""


def build_script_request(
    store: ResearchWorkspaceStore,
    authorization: ProductionAuthorization,
    *,
    working_title: str,
    language: str,
    disclosure: DisclosureBundle,
    constraints: tuple[str, ...] = DEFAULT_SCRIPT_CONSTRAINTS,
) -> ScriptRequest:
    """Build an exportable prompt payload containing only approved product claims."""

    assert_authorization_current(store, authorization)
    grounded: list[GroundedClaim] = []
    for claim in store.list_claims(authorization.product_id):
        if store.current_claim_state(claim.claim_id) is not ClaimState.SUPPORTED:
            continue
        links = [
            link
            for link in store.list_claim_links(claim.claim_id)
            if link.stance is EvidenceStance.SUPPORTS
        ]
        if not links:
            continue
        grounded.append(
            GroundedClaim(
                claim_id=claim.claim_id,
                text=claim.text,
                source_ids=tuple(link.source_id for link in links),
                source_locators=tuple(link.locator for link in links),
            )
        )

    return ScriptRequest(
        product_id=authorization.product_id,
        research_digest=authorization.research_digest,
        language=language,
        working_title=working_title,
        claims=tuple(grounded),
        spoken_disclosure=disclosure.spoken,
        description_disclosure=disclosure.description,
        constraints=constraints,
    )


class StrictTemplateScriptGenerator:
    """Credential-free baseline that repeats approved claim text instead of inventing prose."""

    name = "strict-template-v1"

    def generate(
        self,
        request: ScriptRequest,
        *,
        created_at: datetime | None = None,
    ) -> ScriptDocument:
        moment = datetime.now(UTC) if created_at is None else created_at
        segments: list[ScriptSegment] = [
            ScriptSegment(
                segment_id="intro",
                kind=ScriptSegmentKind.INTRO,
                text=f"Research summary: {request.working_title}.",
            ),
            ScriptSegment(
                segment_id="disclosure",
                kind=ScriptSegmentKind.DISCLOSURE,
                text=request.spoken_disclosure,
            ),
        ]
        for index, claim in enumerate(request.claims, start=1):
            segments.append(
                ScriptSegment(
                    segment_id=f"fact-{index:03d}",
                    kind=ScriptSegmentKind.FACT,
                    text=claim.text,
                    claim_ids=(claim.claim_id,),
                )
            )
        segments.append(
            ScriptSegment(
                segment_id="outro",
                kind=ScriptSegmentKind.OUTRO,
                text="Check the cited product information and current terms before buying.",
            )
        )
        return ScriptDocument(
            product_id=request.product_id,
            research_digest=request.research_digest,
            language=request.language,
            title=request.working_title,
            segments=tuple(segments),
            generator=self.name,
            request_digest=request.digest,
            created_at=moment,
        )


def generate_and_validate_script(
    store: ResearchWorkspaceStore,
    authorization: ProductionAuthorization,
    request: ScriptRequest,
    generator: ScriptGenerator,
) -> ScriptDocument:
    if request.product_id != authorization.product_id:
        raise ValueError("script request belongs to a different product")
    if request.research_digest != authorization.research_digest:
        raise ValueError("script request research digest differs from authorization")
    document = generator.generate(request)
    validate_script_grounding(store, authorization, document)
    return document
