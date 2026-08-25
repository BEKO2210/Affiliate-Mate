"""Explicit currency minor-unit conversion used by realized-outcome accounting."""

from __future__ import annotations

# Currencies supported by the current catalog marketplace layer. The exponent is the number of
# decimal places represented by one major currency unit. Do not silently assume two decimals:
# JPY is a zero-decimal currency.
CURRENCY_MINOR_UNIT_EXPONENTS: dict[str, int] = {
    "AED": 2,
    "AUD": 2,
    "BRL": 2,
    "CAD": 2,
    "EGP": 2,
    "EUR": 2,
    "GBP": 2,
    "INR": 2,
    "JPY": 0,
    "MXN": 2,
    "PLN": 2,
    "SAR": 2,
    "SEK": 2,
    "SGD": 2,
    "TRY": 2,
    "USD": 2,
}


def currency_minor_unit_exponent(currency: str) -> int:
    code = currency.strip().upper()
    if not code:
        raise ValueError("currency must not be empty")
    try:
        return CURRENCY_MINOR_UNIT_EXPONENTS[code]
    except KeyError as exc:
        raise ValueError(
            f"unsupported currency minor-unit exponent: {code}; add an explicit mapping"
        ) from exc


def minor_units_to_major(amount_minor: int, currency: str) -> float:
    """Convert integer minor units without assuming every currency has two decimals."""

    exponent = currency_minor_unit_exponent(currency)
    return amount_minor / (10**exponent)
