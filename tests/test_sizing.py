import math

from metsbrain.config import (
    KELLY_FRACTION_BASE,
    MAX_STAKE_PCT_OF_BANKROLL,
    PACE_FACTOR_MAX,
    PACE_FACTOR_MIN,
)
from metsbrain.sizing import pace_factor, size_bet


def test_pace_factor_at_goal_is_min():
    assert pace_factor(week_profit=100, weekly_goal=100, days_remaining=3) == PACE_FACTOR_MIN


def test_pace_factor_behind_near_end_of_week_scales_up():
    pf = pace_factor(week_profit=0, weekly_goal=100, days_remaining=1)
    assert pf > 1.0
    assert pf <= PACE_FACTOR_MAX


def test_pace_factor_on_pace_is_near_one():
    pf = pace_factor(week_profit=50, weekly_goal=100, days_remaining=3)
    assert math.isclose(pf, 1.0, abs_tol=0.05)


def test_size_bet_respects_max_cap():
    stake = size_bet(
        kelly_full=1.0,
        bankroll=1000,
        risk_tolerance="high",
        week_profit=0,
        weekly_goal=100,
        days_remaining=1,
    )
    assert stake <= MAX_STAKE_PCT_OF_BANKROLL * 1000 + 1e-9


def test_size_bet_zero_kelly_zero_stake():
    assert size_bet(
        kelly_full=0,
        bankroll=1000,
        risk_tolerance="medium",
        week_profit=0,
        weekly_goal=100,
        days_remaining=3,
    ) == 0.0


def test_size_bet_medium_on_pace_matches_base_formula():
    stake = size_bet(
        kelly_full=0.10,
        bankroll=1000,
        risk_tolerance="medium",
        week_profit=50,
        weekly_goal=100,
        days_remaining=3,
    )
    expected = KELLY_FRACTION_BASE * 0.10 * 1.0 * 1.0 * 1000
    expected = min(expected, MAX_STAKE_PCT_OF_BANKROLL * 1000)
    assert abs(stake - expected) < 1.0


def test_pace_factor_override_takes_precedence():
    # Even if naturally-computed pace factor would be high (way behind),
    # the override wins.
    stake_override = size_bet(
        kelly_full=0.10,
        bankroll=1000,
        risk_tolerance="medium",
        week_profit=0,
        weekly_goal=100,
        days_remaining=1,
        pace_factor_override=0.5,
    )
    stake_natural = size_bet(
        kelly_full=0.10,
        bankroll=1000,
        risk_tolerance="medium",
        week_profit=0,
        weekly_goal=100,
        days_remaining=1,
    )
    assert stake_override < stake_natural
