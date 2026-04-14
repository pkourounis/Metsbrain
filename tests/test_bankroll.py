import os
import tempfile

import pytest

from metsbrain import bankroll as br


def test_log_and_settle_win_updates_bankroll():
    s = br.BankrollState(bankroll=1000, weekly_goal=100, risk_tolerance="medium")
    s.ensure_week()
    bet = br.log_bet(s, game_id="g", market="moneyline", side="NYM",
                     american_odds=+150, stake=20)
    br.settle_bet(s, bet.id, "win")
    assert s.bankroll == 1000 + 30.0   # +150 pays 1.5x stake
    assert s.bets[0].result == "win"
    assert s.bets[0].payout == 30.0


def test_settle_loss_debits_bankroll():
    s = br.BankrollState(bankroll=1000, weekly_goal=100, risk_tolerance="medium")
    s.ensure_week()
    bet = br.log_bet(s, game_id="g", market="moneyline", side="NYM",
                     american_odds=-110, stake=22)
    br.settle_bet(s, bet.id, "loss")
    assert s.bankroll == 978.0
    assert s.bets[0].payout == -22.0


def test_cannot_settle_twice():
    s = br.BankrollState(bankroll=1000)
    s.ensure_week()
    bet = br.log_bet(s, game_id="g", market="moneyline", side="NYM",
                     american_odds=-110, stake=22)
    br.settle_bet(s, bet.id, "win")
    with pytest.raises(ValueError):
        br.settle_bet(s, bet.id, "loss")


def test_round_trip_persistence():
    s = br.BankrollState(bankroll=500, weekly_goal=80, risk_tolerance="high")
    s.ensure_week()
    br.log_bet(s, game_id="g", market="total_over", side="over",
               american_odds=-110, stake=15)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "state.json")
        br.save(s, path)
        s2 = br.load(path)
    assert s2.bankroll == 500
    assert s2.weekly_goal == 80
    assert s2.risk_tolerance == "high"
    assert len(s2.bets) == 1
    assert s2.bets[0].stake == 15
