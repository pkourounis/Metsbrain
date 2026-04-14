import os
import tempfile

import pytest

from metsbrain.service import Service
from metsbrain.store import Store


def _svc():
    tmp = tempfile.TemporaryDirectory()
    path = os.path.join(tmp.name, "metsbrain.db")
    return Service(Store(path)), tmp


def test_init_writes_meta_and_week():
    svc, _tmp = _svc()
    svc.init_app(bankroll=1000, weekly_goal=150, risk="medium")
    assert svc.store.get_bankroll() == 1000
    assert svc.store.get_weekly_goal() == 150
    assert svc.store.get_risk_tolerance() == "medium"
    assert svc.store.current_week_starting_bankroll() == 1000


def test_advise_end_to_end_persists_snapshots_and_recs():
    svc, _tmp = _svc()
    svc.init_app(bankroll=1000, weekly_goal=150, risk="medium")
    recs = svc.advise()
    assert len(recs) > 0

    # Snapshots were written (one per sample game).
    n_snap = svc.store._conn.execute(
        "SELECT COUNT(*) AS c FROM feature_snapshots"
    ).fetchone()["c"]
    assert n_snap >= 1

    n_rec = svc.store._conn.execute(
        "SELECT COUNT(*) AS c FROM recommendations"
    ).fetchone()["c"]
    assert n_rec == len(recs)


def test_log_and_settle_updates_bankroll():
    svc, _tmp = _svc()
    svc.init_app(bankroll=1000, weekly_goal=150, risk="medium")

    bet = svc.log_bet(
        game_id="g", market="moneyline", side="NYM",
        american_odds=+150, stake=20.0,
    )
    assert bet.id > 0
    assert svc.store.get_bankroll() == 1000  # no change until settlement

    settled = svc.settle_bet(bet.id, "win")
    assert settled.payout == 30.0
    assert svc.store.get_bankroll() == 1030.0


def test_cannot_settle_twice():
    svc, _tmp = _svc()
    svc.init_app(bankroll=1000, weekly_goal=150, risk="medium")
    bet = svc.log_bet(game_id="g", market="moneyline", side="NYM",
                     american_odds=-110, stake=22)
    svc.settle_bet(bet.id, "win")
    with pytest.raises(ValueError):
        svc.settle_bet(bet.id, "loss")


def test_loss_debits_bankroll():
    svc, _tmp = _svc()
    svc.init_app(bankroll=1000, weekly_goal=150, risk="medium")
    bet = svc.log_bet(game_id="g", market="moneyline", side="NYM",
                     american_odds=-110, stake=22)
    svc.settle_bet(bet.id, "loss")
    assert svc.store.get_bankroll() == 978.0


def test_week_summary_shape():
    svc, _tmp = _svc()
    svc.init_app(bankroll=500, weekly_goal=80, risk="high")
    s = svc.week_summary()
    for k in ("week_anchor", "bankroll", "weekly_goal", "risk_tolerance",
              "week_profit", "days_remaining", "open_bets", "open_risk",
              "starting_bankroll"):
        assert k in s
    assert s["bankroll"] == 500
    assert s["weekly_goal"] == 80
    assert s["risk_tolerance"] == "high"
