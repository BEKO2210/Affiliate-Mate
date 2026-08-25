"""Fail-closed research completeness gates and guarded approval transitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .research_models import ApprovalEvent, ApprovalState, ClaimRisk, ClaimState, EvidenceStance
from .research_store import ResearchWorkspaceStore


@dataclass(frozen=True, slots=True)
class ResearchPolicy:
    """Explicit minimum evidence required before a product can be approved."""

    min_sources: int = 2
    min_distinct_publishers: int = 2
    min_active_claims: int = 1
    min_notes: int = 1
    min_support_sources_per_claim: int = 1
    high_risk_min_support_sources: int = 2
    high_risk_min_distinct_publishers: int = 2
    reject_supported_claims_with_contradictions: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "min_sources",
            "min_distinct_publishers",
            "min_active_claims",
            "min_notes",
            "min_support_sources_per_claim",
            "high_risk_min_support_sources",
            "high_risk_min_distinct_publishers",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResearchCheck:
    code: str
    passed: bool
    actual: int | str
    threshold: int | str
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ResearchCompletenessReport:
    product_id: str
    passed: bool
    checks: tuple[ResearchCheck, ...]
    active_claim_ids: tuple[str, ...]
    rejected_claim_ids: tuple[str, ...]

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(check.message for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
            "failures": list(self.failures),
            "active_claim_ids": list(self.active_claim_ids),
            "rejected_claim_ids": list(self.rejected_claim_ids),
        }


class ResearchApprovalBlocked(RuntimeError):
    """Raised when an approval is requested before completeness gates pass."""

    def __init__(self, report: ResearchCompletenessReport) -> None:
        self.report = report
        details = "; ".join(report.failures) or "research completeness failed"
        super().__init__(f"approval blocked for {report.product_id}: {details}")


def _count_check(code: str, actual: int, threshold: int, label: str) -> ResearchCheck:
    passed = actual >= threshold
    return ResearchCheck(
        code=code,
        passed=passed,
        actual=actual,
        threshold=threshold,
        message=(
            f"{label} passes: {actual} >= {threshold}."
            if passed
            else f"{label} too low: {actual} < {threshold}."
        ),
    )


def evaluate_research_completeness(
    store: ResearchWorkspaceStore,
    product_id: str,
    *,
    policy: ResearchPolicy | None = None,
) -> ResearchCompletenessReport:
    """Evaluate editorial research without inferring or fabricating missing support."""

    active_policy = ResearchPolicy() if policy is None else policy
    sources = store.list_sources(product_id)
    claims = store.list_claims(product_id)
    notes = store.list_notes(product_id)
    publishers = {source.publisher.strip().casefold() for source in sources}

    states = {claim.claim_id: store.current_claim_state(claim.claim_id) for claim in claims}
    active_claims = [claim for claim in claims if states[claim.claim_id] is not ClaimState.REJECTED]
    rejected_claims = [claim for claim in claims if states[claim.claim_id] is ClaimState.REJECTED]

    checks: list[ResearchCheck] = [
        _count_check("sources", len(sources), active_policy.min_sources, "Research sources"),
        _count_check(
            "distinct_publishers",
            len(publishers),
            active_policy.min_distinct_publishers,
            "Distinct source publishers",
        ),
        _count_check(
            "active_claims",
            len(active_claims),
            active_policy.min_active_claims,
            "Active claims",
        ),
        _count_check("notes", len(notes), active_policy.min_notes, "Research notes"),
    ]

    linked_note_claims = {
        claim_id
        for note in notes
        for claim_id in store.note_claim_ids(note.note_id)
    }
    if active_claims:
        missing_note_claims = sorted(
            claim.claim_id for claim in active_claims if claim.claim_id not in linked_note_claims
        )
        checks.append(
            ResearchCheck(
                code="claim_note_coverage",
                passed=not missing_note_claims,
                actual="complete" if not missing_note_claims else ", ".join(missing_note_claims),
                threshold="every active claim linked from a note",
                message=(
                    "Every active claim is represented in citation-ready notes."
                    if not missing_note_claims
                    else "Active claims missing from research notes: " + ", ".join(missing_note_claims)
                ),
            )
        )

    source_by_id = {source.source_id: source for source in sources}
    for claim in active_claims:
        state = states[claim.claim_id]
        checks.append(
            ResearchCheck(
                code=f"claim_state:{claim.claim_id}",
                passed=state is ClaimState.SUPPORTED,
                actual=state.value,
                threshold=ClaimState.SUPPORTED.value,
                message=(
                    f"Claim {claim.claim_id} is explicitly supported."
                    if state is ClaimState.SUPPORTED
                    else f"Claim {claim.claim_id} is {state.value}, not supported."
                ),
            )
        )
        links = store.list_claim_links(claim.claim_id)
        support_links = [link for link in links if link.stance is EvidenceStance.SUPPORTS]
        contradict_links = [link for link in links if link.stance is EvidenceStance.CONTRADICTS]
        required_support = (
            active_policy.high_risk_min_support_sources
            if claim.risk is ClaimRisk.HIGH
            else active_policy.min_support_sources_per_claim
        )
        distinct_support_sources = {link.source_id for link in support_links}
        checks.append(
            _count_check(
                f"claim_support:{claim.claim_id}",
                len(distinct_support_sources),
                required_support,
                f"Support sources for claim {claim.claim_id}",
            )
        )
        if claim.risk is ClaimRisk.HIGH:
            support_publishers = {
                source_by_id[source_id].publisher.strip().casefold()
                for source_id in distinct_support_sources
                if source_id in source_by_id
            }
            checks.append(
                _count_check(
                    f"claim_publisher_diversity:{claim.claim_id}",
                    len(support_publishers),
                    active_policy.high_risk_min_distinct_publishers,
                    f"Independent publishers for high-risk claim {claim.claim_id}",
                )
            )
        if active_policy.reject_supported_claims_with_contradictions:
            checks.append(
                ResearchCheck(
                    code=f"claim_contradictions:{claim.claim_id}",
                    passed=not contradict_links,
                    actual=len(contradict_links),
                    threshold=0,
                    message=(
                        f"Claim {claim.claim_id} has no unresolved contradictory evidence."
                        if not contradict_links
                        else f"Claim {claim.claim_id} has {len(contradict_links)} contradictory evidence link(s)."
                    ),
                )
            )

    result_checks = tuple(checks)
    return ResearchCompletenessReport(
        product_id=product_id,
        passed=all(check.passed for check in result_checks),
        checks=result_checks,
        active_claim_ids=tuple(claim.claim_id for claim in active_claims),
        rejected_claim_ids=tuple(claim.claim_id for claim in rejected_claims),
    )


def transition_product_approval(
    store: ResearchWorkspaceStore,
    product_id: str,
    state: ApprovalState,
    *,
    actor: str,
    reason: str,
    expected_state: ApprovalState | None = None,
    policy: ResearchPolicy | None = None,
) -> ApprovalEvent:
    """Transition approval state, refusing APPROVED until research gates pass."""

    if state is ApprovalState.APPROVED:
        report = evaluate_research_completeness(store, product_id, policy=policy)
        if not report.passed:
            raise ResearchApprovalBlocked(report)
    return store.transition_approval(
        product_id,
        state,
        actor=actor,
        reason=reason,
        expected_state=expected_state,
    )
