import os
import tempfile

from metsbrain.models import LoggedBet
from metsbrain.store import Store, this_monday


def _tmp_store():
    tmp = tempfile.TemporaryDirectory()
    path = os.path.join(tmp.name, "metsbrain.db")
    return Store(path), tmp  # caller holds tmp to keep dir alive


def test_meta_roundtrip():
    store, _tmp = _tmp_store()
    store.set_bankroll(1234.56)
    store.set_meta("weekly_goal", "150.00")
    store.set_meta("risk_tolerance", "high")
    assert store.get_bankroll() == 1234.56
    assert store.get_weekly_goal() == 150.0
    assert store.get_risk_tolerance() == "high"


def test_ensure_week_creates_row_once():
    store, _tmp = _tmp_store()
    a1 = store.ensure_week(bankroll=1000, weekly_goal=150, risk="medium")
    a2 = store.ensure_week(bankroll=999, weekly_goal=150, risk="medium")
    assert a1 == a2 == this_monday()
    assert store.current_week_starting_bankroll() == 1000.0


def test_insert_and_settle_bet_affects_week_profit():
    store, _tmp = _tmp_store()
    store.set_bankroll(1000)
    store.ensure_week(bankroll=1000, weekly_goal=150, risk="medium")

    bet = LoggedBet(
        id=0, game_id="g", market="moneyline", side="NYM",
        american_odds=+150, stake=20.0, placed_on=this_monday(),
    )
    bet_id = store.insert_bet(bet)
    assert bet_id > 0

    # Open bets don't count toward week profit.
    assert store.week_profit() == 0.0

    store.update_bet_settlement(bet_id, "win", 30.0)
    assert store.week_profit() == 30.0

    got = store.get_bet(bet_id)
    assert got is not None
    assert got.result == "win"
    assert got.payout == 30.0


def test_list_bets_filters_open():
    store, _tmp = _tmp_store()
    for odds in (+150, -110):
        store.insert_bet(LoggedBet(
            id=0, game_id="g", market="moneyline", side="NYM",
            american_odds=odds, stake=20.0, placed_on=this_monday(),
        ))
    open_bets = store.list_bets(only_open=True)
    assert len(open_bets) == 2

    store.update_bet_settlement(open_bets[0].id, "loss", -20.0)
    assert len(store.list_bets(only_open=True)) == 1
