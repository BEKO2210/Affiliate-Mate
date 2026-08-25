"""Provider orchestration with validation, health reporting, and atomic persistence."""

from dataclasses import dataclass
from enum import StrEnum

from .evidence import EvidenceObservation, SQLiteEvidenceStore
from .models import ProductCandidate
from .providers import EvidenceProvider


class ProviderRunStatus(StrEnum):
    SUCCESS = "success"
    EMPTY = "empty"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProviderRunResult:
    provider: str
    status: ProviderRunStatus
    observations: int
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceCollectionReport:
    product_id: str
    marketplace: str
    provider_results: tuple[ProviderRunResult, ...]
    observations_collected: int
    observations_stored: int

    @property
    def failed_providers(self) -> tuple[str, ...]:
        return tuple(
            result.provider
            for result in self.provider_results
            if result.status == ProviderRunStatus.FAILED
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "product_id": self.product_id,
            "marketplace": self.marketplace,
            "observations_collected": self.observations_collected,
            "observations_stored": self.observations_stored,
            "failed_providers": list(self.failed_providers),
            "providers": [
                {
                    "provider": result.provider,
                    "status": result.status.value,
                    "observations": result.observations,
                    "error_type": result.error_type,
                    "error_message": result.error_message,
                }
                for result in self.provider_results
            ],
        }


def _validate_observation(
    candidate: ProductCandidate,
    provider_name: str,
    observation: EvidenceObservation,
) -> None:
    if observation.product_id != candidate.product_id:
        raise ValueError(
            f"provider {provider_name!r} returned evidence for a different product_id"
        )
    if observation.marketplace.upper() != candidate.marketplace.upper():
        raise ValueError(
            f"provider {provider_name!r} returned evidence for a different marketplace"
        )


def collect_evidence(
    candidate: ProductCandidate,
    providers: list[EvidenceProvider],
    *,
    store: SQLiteEvidenceStore | None = None,
    fail_fast: bool = False,
) -> EvidenceCollectionReport:
    """Collect independent provider evidence and persist successful results atomically."""

    collected: list[EvidenceObservation] = []
    results: list[ProviderRunResult] = []
    for provider in providers:
        name = provider.name
        try:
            observations = list(provider.collect(candidate))
            for observation in observations:
                _validate_observation(candidate, name, observation)
        except Exception as exc:
            if fail_fast:
                raise
            results.append(
                ProviderRunResult(
                    provider=name,
                    status=ProviderRunStatus.FAILED,
                    observations=0,
                    error_type=type(exc).__name__,
                    error_message=str(exc)[:300],
                )
            )
            continue

        collected.extend(observations)
        results.append(
            ProviderRunResult(
                provider=name,
                status=(
                    ProviderRunStatus.SUCCESS
                    if observations
                    else ProviderRunStatus.EMPTY
                ),
                observations=len(observations),
            )
        )

    stored = store.add_many(collected) if store is not None and collected else 0
    return EvidenceCollectionReport(
        product_id=candidate.product_id,
        marketplace=candidate.marketplace.upper(),
        provider_results=tuple(results),
        observations_collected=len(collected),
        observations_stored=stored,
    )
