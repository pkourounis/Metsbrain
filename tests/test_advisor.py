from dataclasses import replace
from datetime import date, timedelta

from metsbrain.advisor import recommend
from metsbrain.config import MAX_BETS_PER_DAY, MAX_STAKE_PCT_PER_GAME
from metsbrain.data import SampleDataProvider
from metsbrain.models import (
    BatterProfile,
    Game,
    GameContext,
    OfferedLine,
    PitcherLine,
    TeamForm,
)


def _recs(**overrides):
    kwargs = dict(
        bankroll=1000,
        starting_bankroll_this_week=1000,
        weekly_goal=150,
        week_profit=0,
        days_remaining=5,
        risk_tolerance="medium",
    )
    kwargs.update(overrides)
    games = SampleDataProvider().upcoming_games()
    return recommend(games, **kwargs)


def test_advise_returns_sorted_plays():
    recs = _recs()
    assert len(recs) > 0
    for a, b in zip(recs, recs[1:]):
        assert a.edge >= b.edge
    for r in recs:
        assert 0 < r.stake <= 50 + 0.01
        assert 0 <= r.model_prob <= 1
        assert r.edge > 0
        assert r.rationale


def test_max_three_bets_per_day():
    recs = _recs(risk_tolerance="high")
    by_day: dict[str, int] = {}
    for r in recs:
        by_day[r.game_date] = by_day.get(r.game_date, 0) + 1
    for count in by_day.values():
        assert count <= MAX_BETS_PER_DAY


def test_correlation_cap_per_game():
    recs = _recs(risk_tolerance="high")
    by_game: dict[str, float] = {}
    for r in recs:
        by_game[r.game_id] = by_game.get(r.game_id, 0.0) + r.stake
    cap = MAX_STAKE_PCT_PER_GAME * 1000
    for total in by_game.values():
        assert total <= cap + 0.01


def test_low_risk_only_surfaces_low_bucket():
    recs = _recs(risk_tolerance="low")
    for r in recs:
        assert r.risk_bucket == "low"


def test_goal_hit_triggers_lockdown():
    """Once week profit >= goal, only low-risk picks surface with a lockdown banner."""
    recs_locked = _recs(risk_tolerance="high", week_profit=200)
    for r in recs_locked:
        assert r.risk_bucket == "low"
        assert any("lockdown" in note.lower() for note in r.rationale)


def test_weekly_drawdown_cooldown_returns_nothing():
    # Started week at 1000, now at 700 → 30% drawdown → cool-down.
    recs = _recs(bankroll=700, starting_bankroll_this_week=1000, risk_tolerance="high")
    assert recs == []


def test_no_bankroll_no_stakes():
    recs = _recs(bankroll=0, starting_bankroll_this_week=0)
    assert recs == []


def _prop_only_game():
    """A minimal game exposing only prop markets, so the advisor's prop
    pathway can be exercised without the Mets ML/RL picks eating the top-3."""
    d = (date.today() + timedelta(days=1)).isoformat()
    return Game(
        game_id=f"NYM-propday-{d}",
        date=d,
        opponent="OPP",
        mets_pitcher=PitcherLine("AceSP", era=3.00, fip=3.20, whip=1.10,
                                 k_per_9=11.0, expected_ip=6.5, hr_per_9=0.9),
        opp_pitcher=PitcherLine("SoftSP", era=5.20, fip=5.00, whip=1.50,
                                k_per_9=6.5, expected_ip=5.0, hr_per_9=1.70),
        mets_form=TeamForm(),
        opp_form=TeamForm(),
        context=GameContext(home=True, park_factor_runs=1.05),
        mets_lineup=[
            BatterProfile("Alonso", hr_per_pa=0.055, batting_avg=0.260, vs_hand_boost=1.10),
        ],
        offered=[
            # Very soft lines to guarantee +EV surfacing.
            OfferedLine("prop_hr",          "yes",  +500, player="Alonso"),
            OfferedLine("prop_sp_ks_over",  "over", +100, threshold=5.5),
        ],
    )


def test_prop_pathway_surfaces_edges():
    recs = recommend(
        [_prop_only_game()],
        bankroll=1000,
        starting_bankroll_this_week=1000,
        weekly_goal=150,
        week_profit=0,
        days_remaining=5,
        risk_tolerance="high",
    )
    markets = {r.market for r in recs}
    assert "prop_sp_ks_over" in markets  # always surfaces with these inputs


def test_prop_rationale_is_prop_specific():
    recs = recommend(
        [_prop_only_game()],
        bankroll=1000,
        starting_bankroll_this_week=1000,
        weekly_goal=150,
        week_profit=0,
        days_remaining=5,
        risk_tolerance="high",
    )
    prop_rec = next(r for r in recs if r.market == "prop_sp_ks_over")
    joined = " ".join(prop_rec.rationale).lower()
    assert "k/9" in joined or "ks" in joined
