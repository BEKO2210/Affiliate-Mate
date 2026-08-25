"""Explicit affiliate-disclosure helpers.

Templates are convenience defaults, not a legal-compliance oracle. Callers can replace either
string before production. Publication remains the user's responsibility.
"""

from __future__ import annotations

from .production_models import DisclosureBundle


def disclosure_template(*, locale: str, network: str = "affiliate") -> DisclosureBundle:
    normalized_locale = locale.strip().lower().replace("_", "-")
    normalized_network = network.strip() or "affiliate"

    if normalized_locale.startswith("de"):
        return DisclosureBundle(
            locale=normalized_locale,
            network=normalized_network,
            spoken=(
                "Hinweis: Dieses Video enthält Affiliate-Links. Wenn du darüber etwas kaufst, "
                "kann ich eine Provision erhalten, ohne dass dir dadurch Mehrkosten entstehen."
            ),
            description=(
                "Hinweis: Diese Beschreibung enthält Affiliate-Links. Bei einem qualifizierten "
                "Kauf kann ich eine Provision erhalten, ohne Mehrkosten für dich."
            ),
        )
    if normalized_locale.startswith("en"):
        return DisclosureBundle(
            locale=normalized_locale,
            network=normalized_network,
            spoken=(
                "Disclosure: this video contains affiliate links. If you buy through them, "
                "I may earn a commission at no additional cost to you."
            ),
            description=(
                "Disclosure: this description contains affiliate links. I may earn a commission "
                "from qualifying purchases at no additional cost to you."
            ),
        )
    raise ValueError(
        f"no built-in disclosure template for locale {locale!r}; provide an explicit bundle"
    )
