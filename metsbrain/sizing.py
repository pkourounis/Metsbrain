"""Bet sizing: fractional Kelly, bent around the weekly revenue goal."""

from __future__ import annotations

from .config import (
    KELLY_FRACTION_BASE,
    MAX_STAKE_PCT_OF_BANKROLL,
    PACE_FACTOR_MAX,
    PACE_FACTOR_MIN,
    RISK_PROFILES,
)


def pace_factor(week_profit: float, weekly_goal: float, days_remaining: int) -> float:
    """Return a multiplier on Kelly fraction based on weekly-goal progress.

    - If already at/above goal, dial way back (PACE_FACTOR_MIN).
    - If behind pace with the week almost over, dial up (capped at PACE_FACTOR_MAX).
    - Otherwise linearly interpolate.
    """
    if weekly_goal <= 0:
        return 1.0
    if week_profit >= weekly_goal:
        return PACE_FACTOR_MIN

    days_remaining = max(1, min(days_remaining, 7))
    expected_progress = (7 - days_remaining) / 7.0 * weekly_goal
    shortfall = expected_progress - week_profit  # positive = behind pace

    # Normalize shortfall by weekly_goal → roughly [-1, 1].
    normalized = max(-1.0, min(1.0, shortfall / weekly_goal))

    # Behind pace (normalized > 0) → scale up toward PACE_FACTOR_MAX.
    # Ahead of pace (normalized < 0) → scale down toward PACE_FACTOR_MIN.
    if normalized >= 0:
        return 1.0 + normalized * (PACE_FACTOR_MAX - 1.0)
    return 1.0 + normalized * (1.0 - PACE_FACTOR_MIN)


def size_bet(
    *,
    kelly_full: float,
    bankroll: float,
    risk_tolerance: str,
    week_profit: float,
    weekly_goal: float,
    days_remaining: int,
) -> float:
    """Return a dollar stake, already capped by the max-stake rule."""
    if kelly_full <= 0 or bankroll <= 0:
        return 0.0

    profile = RISK_PROFILES[risk_tolerance]
    pf = pace_factor(week_profit, weekly_goal, days_remaining)

    fraction = (
        KELLY_FRACTION_BASE
        * kelly_full
        * profile["size_mult"]
        * pf
    )
    stake = fraction * bankroll
    cap = MAX_STAKE_PCT_OF_BANKROLL * bankroll
    return max(0.0, min(stake, cap))
