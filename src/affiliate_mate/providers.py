"""Provider contracts that keep acquisition code outside the decision engine."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from .evidence import EvidenceObservation
from .models import ProductCandidate


@runtime_checkable
class CandidateProvider(Protocol):
    """A source that yields normalized product candidates."""

    @property
    def name(self) -> str: ...

    def candidates(self) -> Iterable[ProductCandidate]: ...


@runtime_checkable
class EvidenceProvider(Protocol):
    """A source that collects evidence without making opportunity decisions."""

    @property
    def name(self) -> str: ...

    def collect(self, candidate: ProductCandidate) -> Iterable[EvidenceObservation]: ...
