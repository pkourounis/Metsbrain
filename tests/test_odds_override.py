"""The DB-stored odds override must actually flow into the advisor pipeline."""

import os
import tempfile

from metsbrain.service import Service
from metsbrain.store import Store


def test_db_override_replaces_sample_line():
    tmp = tempfile.TemporaryDirectory()
    path = os.path.join(tmp.name, "metsbrain.db")
    svc = Service(Store(path))
    svc.init_app(bankroll=1000, weekly_goal=150, risk="medium")

    games_before = svc.upcoming_games()
    target = games_before[0]
    orig_ml = next(ln for ln in target.offered
                   if ln.market == "moneyline" and ln.side == "NYM")

    # Push an override at very different odds.
    svc.enter_odds(
        game_id=target.game_id,
        market="moneyline", side="NYM", american_odds=-101,
    )

    games_after = svc.upcoming_games()
    target_after = next(g for g in games_after if g.game_id == target.game_id)
    ml_after = next(ln for ln in target_after.offered
                    if ln.market == "moneyline" and ln.side == "NYM")

    assert ml_after.american_odds == -101
    assert ml_after.american_odds != orig_ml.american_odds

    svc.store.close()
    tmp.cleanup()


def test_db_override_adds_new_line():
    tmp = tempfile.TemporaryDirectory()
    path = os.path.join(tmp.name, "metsbrain.db")
    svc = Service(Store(path))
    svc.init_app(bankroll=1000, weekly_goal=150, risk="medium")

    games = svc.upcoming_games()
    target = games[0]
    n_before = len(target.offered)

    # Add a completely new prop line.
    svc.enter_odds(
        game_id=target.game_id,
        market="prop_hits_over", side="under",
        player="Nimmo", threshold=0.5,
        american_odds=+130,
    )

    games_after = svc.upcoming_games()
    target_after = next(g for g in games_after if g.game_id == target.game_id)
    assert len(target_after.offered) == n_before + 1
    assert any(
        ln.market == "prop_hits_over" and ln.side == "under"
        and ln.player == "Nimmo" and ln.threshold == 0.5
        and ln.american_odds == +130
        for ln in target_after.offered
    )

    svc.store.close()
    tmp.cleanup()
