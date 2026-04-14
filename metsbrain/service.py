"""High-level application operations.

Wraps the Store, DataProvider, and Advisor. CLI (now) and the web UI (later)
both drive the app through this layer so they stay behaviorally identical.
"""

from __future__ import annotations

from datetime import datetime

from . import analysis
from .advisor import recommend
from .data import SampleDataProvider
from .models import LoggedBet, Recommendation
from .odds import net_profit_per_unit
from .store import Store


class Service:
    def __init__(self, store: Store, data_provider=None):
        self.store = store
        self.data_provider = data_provider or SampleDataProvider()

    # --- setup ---------------------------------------------------------------

    def init_app(self, *, bankroll: float, weekly_goal: float, risk: str) -> None:
        self.store.set_bankroll(bankroll)
        self.store.set_meta("weekly_goal", f"{weekly_goal:.2f}")
        self.store.set_meta("risk_tolerance", risk)
        self.store.ensure_week(
            bankroll=bankroll, weekly_goal=weekly_goal, risk=risk
        )

    # --- advise --------------------------------------------------------------

    def advise(self, *, persist: bool = True) -> list[Recommendation]:
        bankroll = self.store.get_bankroll()
        goal = self.store.get_weekly_goal()
        risk = self.store.get_risk_tolerance()
        self.store.ensure_week(bankroll=bankroll, weekly_goal=goal, risk=risk)

        week_profit = self.store.week_profit()
        days_left = self.store.days_remaining_in_week()
        starting = self.store.current_week_starting_bankroll()

        games = self.data_provider.upcoming_games()

        if persist:
            for g in games:
                probs = analysis.evaluate(g)
                self.store.save_snapshot(g.game_id, {
                    "p_win": probs["p_win"],
                    "p_f5_win": probs["p_f5_win"],
                    "p_over": probs["p_over"],
                    "p_under": probs["p_under"],
                    "features": [f.to_dict() for f in probs["features"]],
                })

        recs = recommend(
            games,
            bankroll=bankroll,
            starting_bankroll_this_week=starting,
            weekly_goal=goal,
            week_profit=week_profit,
            days_remaining=days_left,
            risk_tolerance=risk,
        )

        if persist:
            for r in recs:
                self.store.save_recommendation(r)

        return recs

    # --- bet log / settle ----------------------------------------------------

    def log_bet(
        self,
        *,
        game_id: str,
        market: str,
        side: str,
        american_odds: int,
        stake: float,
        player: str | None = None,
        threshold: float | None = None,
        line: float | None = None,
        recommendation_id: int | None = None,
    ) -> LoggedBet:
        bet = LoggedBet(
            id=0,
            game_id=game_id,
            market=market,
            side=side,
            american_odds=american_odds,
            stake=float(stake),
            placed_on=datetime.now().date().isoformat(),
            player=player,
            threshold=threshold,
            line=line,
            recommendation_id=recommendation_id,
        )
        bet.id = self.store.insert_bet(bet)
        return bet

    def settle_bet(self, bet_id: int, result: str) -> LoggedBet:
        if result not in {"win", "loss", "push"}:
            raise ValueError("result must be win, loss, or push")
        bet = self.store.get_bet(bet_id)
        if bet is None:
            raise KeyError(f"no bet with id {bet_id}")
        if bet.result != "open":
            raise ValueError(f"bet {bet_id} already settled as {bet.result}")

        if result == "win":
            payout = round(bet.stake * net_profit_per_unit(bet.american_odds), 2)
        elif result == "loss":
            payout = round(-bet.stake, 2)
        else:
            payout = 0.0

        self.store.update_bet_settlement(bet_id, result, payout)
        new_bankroll = self.store.get_bankroll() + payout
        self.store.set_bankroll(new_bankroll)

        bet.result = result
        bet.payout = payout
        return bet

    # --- reporting -----------------------------------------------------------

    def week_summary(self) -> dict:
        bankroll = self.store.get_bankroll()
        goal = self.store.get_weekly_goal()
        risk = self.store.get_risk_tolerance()
        self.store.ensure_week(bankroll=bankroll, weekly_goal=goal, risk=risk)

        from .store import this_monday
        anchor = this_monday()
        profit = self.store.week_profit()
        open_bets = self.store.list_bets(since=anchor, only_open=True)
        return {
            "week_anchor": anchor,
            "bankroll": bankroll,
            "weekly_goal": goal,
            "risk_tolerance": risk,
            "week_profit": profit,
            "days_remaining": self.store.days_remaining_in_week(),
            "open_bets": open_bets,
            "open_risk": sum(b.stake for b in open_bets),
            "starting_bankroll": self.store.current_week_starting_bankroll(),
        }
