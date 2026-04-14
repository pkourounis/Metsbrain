from metsbrain.advisor import recommend
from metsbrain.data import SampleDataProvider


def test_advise_on_sample_data_returns_sorted_recs():
    games = SampleDataProvider().upcoming_games()
    recs = recommend(
        games,
        bankroll=1000,
        weekly_goal=150,
        week_profit=0,
        days_remaining=5,
        risk_tolerance="medium",
    )
    # Sample data is rigged so at least one +EV pick exists somewhere.
    assert len(recs) > 0

    # Edges should be non-increasing.
    for a, b in zip(recs, recs[1:]):
        assert a.edge >= b.edge

    for r in recs:
        assert 0 < r.stake <= 50   # 5% cap of 1000
        assert 0 <= r.model_prob <= 1
        assert r.edge > 0
        assert r.risk_bucket in {"low", "medium", "high"}
        assert r.rationale


def test_low_risk_only_surfaces_low_bucket_plays():
    games = SampleDataProvider().upcoming_games()
    recs = recommend(
        games,
        bankroll=1000,
        weekly_goal=150,
        week_profit=0,
        days_remaining=5,
        risk_tolerance="low",
    )
    for r in recs:
        assert r.risk_bucket == "low"


def test_no_bankroll_no_stakes():
    games = SampleDataProvider().upcoming_games()
    recs = recommend(
        games,
        bankroll=0,
        weekly_goal=150,
        week_profit=0,
        days_remaining=5,
        risk_tolerance="medium",
    )
    assert recs == []
