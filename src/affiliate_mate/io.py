"""Input helpers for provider-neutral candidate data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .models import ProductCandidate


@dataclass(frozen=True, slots=True)
class CandidateInput:
    """A candidate plus the fields that were explicitly present in its input source."""

    candidate: ProductCandidate
    provided_fields: frozenset[str]


def _load_rows(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"product_id", "title", "price", "commission_rate"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
        return [dict(row) for row in reader]


def load_candidate_inputs_csv(path: str | Path) -> list[CandidateInput]:
    """Load candidates while preserving which evidence fields were explicitly supplied."""

    inputs: list[CandidateInput] = []
    for row in _load_rows(path):
        provided = frozenset(
            key for key, value in row.items() if value is not None and str(value).strip() != ""
        )
        inputs.append(
            CandidateInput(
                candidate=ProductCandidate.from_mapping(row),
                provided_fields=provided,
            )
        )
    return inputs


def load_candidates_csv(path: str | Path) -> list[ProductCandidate]:
    """Load normalized candidates from CSV."""

    return [item.candidate for item in load_candidate_inputs_csv(path)]
