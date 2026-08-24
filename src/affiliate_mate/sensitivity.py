"""Deterministic sensitivity analysis for CTR and conversion assumptions."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ProductCandidate


@dataclass(frozen=True, slots=True)
class SensitivityPoint:
    ctr_multiplier: float
    conversion_multiplier: float
    estimated_ctr: float
    estimated_conversion_rate: float
    estimated_value_per_1000_views: float

    def to_dict(self) -> dict[str, float]:
        return {
            "ctr_multiplier": self.ctr_multiplier,
            "conversion_multiplier": self.conversion_multiplier,
            "estimated_ctr": self.estimated_ctr,
            "estimated_conversion_rate": self.estimated_conversion_rate,
            "estimated_value_per_1000_views": self.estimated_value_per_1000_views,
        }


@dataclass(frozen=True, slots=True)
class SensitivityReport:
    floor_ev_per_1000_views: float
    base_ev_per_1000_views: float
    ceiling_ev_per_1000_views: float
    points: tuple[SensitivityPoint, ...]

    @property
    def downside_from_base_percent(self) -> float:
        if self.base_ev_per_1000_views == 0:
            return 0.0
        return round(
            ((self.floor_ev_per_1000_views / self.base_ev_per_1000_views) - 1) * 100,
            2,
        )

    @property
    def upside_from_base_percent(self) -> float:
        if self.base_ev_per_1000_views == 0:
            return 0.0
        return round(
            ((self.ceiling_ev_per_1000_views / self.base_ev_per_1000_views) - 1) * 100,
            2,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "floor_ev_per_1000_views": self.floor_ev_per_1000_views,
            "base_ev_per_1000_views": self.base_ev_per_1000_views,
            "ceiling_ev_per_1000_views": self.ceiling_ev_per_1000_views,
            "downside_from_base_percent": self.downside_from_base_percent,
            "upside_from_base_percent": self.upside_from_base_percent,
            "points": [point.to_dict() for point in self.points],
        }


def analyze_sensitivity(
    candidate: ProductCandidate,
    *,
    ctr_multipliers: tuple[float, ...] = (0.6, 1.0, 1.4),
    conversion_multipliers: tuple[float, ...] = (0.6, 1.0, 1.4),
) -> SensitivityReport:
    """Evaluate a small grid around the candidate's explicit CTR/conversion assumptions."""

    if not ctr_multipliers or not conversion_multipliers:
        raise ValueError("sensitivity multiplier sets must not be empty")
    if any(multiplier <= 0 for multiplier in (*ctr_multipliers, *conversion_multipliers)):
        raise ValueError("sensitivity multipliers must be > 0")

    points: list[SensitivityPoint] = []
    for ctr_multiplier in ctr_multipliers:
        for conversion_multiplier in conversion_multipliers:
            ctr = min(1.0, candidate.estimated_ctr * ctr_multiplier)
            conversion = min(
                1.0,
                candidate.estimated_conversion_rate * conversion_multiplier,
            )
            ev = 1000 * ctr * conversion * candidate.commission_per_sale
            points.append(
                SensitivityPoint(
                    ctr_multiplier=ctr_multiplier,
                    conversion_multiplier=conversion_multiplier,
                    estimated_ctr=round(ctr, 6),
                    estimated_conversion_rate=round(conversion, 6),
                    estimated_value_per_1000_views=round(ev, 2),
                )
            )

    values = [point.estimated_value_per_1000_views for point in points]
    return SensitivityReport(
        floor_ev_per_1000_views=min(values),
        base_ev_per_1000_views=round(candidate.estimated_value_per_1000_views, 2),
        ceiling_ev_per_1000_views=max(values),
        points=tuple(points),
    )
