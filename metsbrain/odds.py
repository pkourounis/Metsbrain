"""American-odds helpers. Kept tiny and standalone so they're easy to unit test."""

from __future__ import annotations


def american_to_decimal(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be 0")
    if odds > 0:
        return 1 + odds / 100.0
    return 1 + 100.0 / abs(odds)


def american_to_implied(odds: int) -> float:
    """Raw implied probability (still contains the book's vig)."""
    d = american_to_decimal(odds)
    return 1.0 / d


def devig_two_way(odds_a: int, odds_b: int) -> tuple[float, float]:
    """Return devigged fair probabilities for a two-way market."""
    ia = american_to_implied(odds_a)
    ib = american_to_implied(odds_b)
    total = ia + ib
    return ia / total, ib / total


def net_profit_per_unit(odds: int) -> float:
    """How many units of profit a 1-unit winning bet returns."""
    return american_to_decimal(odds) - 1.0


def kelly_fraction(p: float, odds: int) -> float:
    """Full-Kelly optimal fraction. Returns 0 when the bet has no edge."""
    b = net_profit_per_unit(odds)
    q = 1 - p
    f = (b * p - q) / b
    return max(0.0, f)
