"""Fail-closed authorization and script-grounding checks for production."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .production_models import ProductionAuthorization, ScriptDocument, ScriptSegmentKind
from .research_models import ClaimState
from .research_policy import ApprovalGuardReport, evaluate_approval_guard
from .research_store import ResearchWorkspaceStore


class ProductionAuthorizationError(RuntimeError):
    """Raised when production attempts to cross a stale or incomplete approval boundary."""


class ScriptGroundingError(ValueError):
    """Raised when a script references claims outside the approved research package."""


@dataclass(frozen=True, slots=True)
class AuthorizationCheck:
    passed: bool
    guard: ApprovalGuardReport
    authorization: ProductionAuthorization | None
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "guard": self.guard.to_dict(),
            "authorization": None if self.authorization is None else self.authorization.to_dict(),
            "failures": list(self.failures),
        }


def evaluate_production_authorization(
    store: ResearchWorkspaceStore,
    product_id: str,
    *,
    created_at: datetime | None = None,
) -> AuthorizationCheck:
    """Translate the research approval guard into a production capability token."""

    guard = evaluate_approval_guard(store, product_id)
    failures = list(guard.failures)
    authorization = None
    if guard.passed:
        if guard.approved_event_id is None or guard.approved_research_digest is None:
            failures.append("approval guard passed without persistent approval lineage")
        else:
            moment = datetime.now(UTC) if created_at is None else created_at
            authorization = ProductionAuthorization(
                product_id=product_id,
                approval_event_id=guard.approved_event_id,
                research_digest=guard.approved_research_digest,
                created_at=moment,
            )
    return AuthorizationCheck(
        passed=guard.passed and authorization is not None and not failures,
        guard=guard,
        authorization=authorization,
        failures=tuple(failures),
    )


def require_production_authorization(
    store: ResearchWorkspaceStore,
    product_id: str,
) -> ProductionAuthorization:
    check = evaluate_production_authorization(store, product_id)
    if not check.passed or check.authorization is None:
        details = "; ".join(check.failures) or "production authorization failed"
        raise ProductionAuthorizationError(f"{product_id}: {details}")
    return check.authorization


def assert_authorization_current(
    store: ResearchWorkspaceStore,
    authorization: ProductionAuthorization,
) -> ApprovalGuardReport:
    """Re-check approval at the point of use to prevent stale capability reuse."""

    guard = evaluate_approval_guard(store, authorization.product_id)
    failures = list(guard.failures)
    if guard.approved_event_id != authorization.approval_event_id:
        failures.append("approval event changed after production authorization was created")
    if guard.current_research_digest != authorization.research_digest:
        failures.append("research digest changed after production authorization was created")
    if failures or not guard.passed:
        raise ProductionAuthorizationError(
            f"{authorization.product_id}: " + "; ".join(dict.fromkeys(failures))
        )
    return guard


def validate_script_grounding(
    store: ResearchWorkspaceStore,
    authorization: ProductionAuthorization,
    script: ScriptDocument,
) -> None:
    """Require every factual script segment to reference supported claims from this product."""

    assert_authorization_current(store, authorization)
    if script.product_id != authorization.product_id:
        raise ScriptGroundingError("script belongs to a different product")
    if script.research_digest != authorization.research_digest:
        raise ScriptGroundingError("script research digest differs from authorization")

    claims = {claim.claim_id: claim for claim in store.list_claims(authorization.product_id)}
    allowed_claim_ids = {
        claim_id
        for claim_id in claims
        if store.current_claim_state(claim_id) is ClaimState.SUPPORTED
    }
    referenced_claim_ids: set[str] = set()
    for segment in script.segments:
        if segment.kind is ScriptSegmentKind.FACT and not segment.claim_ids:
            raise ScriptGroundingError(f"factual segment {segment.segment_id} has no claim IDs")
        for claim_id in segment.claim_ids:
            if claim_id not in allowed_claim_ids:
                raise ScriptGroundingError(
                    f"segment {segment.segment_id} references unavailable claim {claim_id}"
                )
            referenced_claim_ids.add(claim_id)

    if not referenced_claim_ids:
        raise ScriptGroundingError("script must reference at least one approved research claim")
