"""Input helpers for provider-neutral candidate data."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import ProductCandidate


def load_candidates_csv(path: str | Path) -> list[ProductCandidate]:
    """Load normalized candidates from CSV."""

    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"product_id", "title", "price", "commission_rate"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
        return [ProductCandidate.from_mapping(row) for row in reader]
