"""JSON-persisted bankroll + weekly-goal + bet-log state."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta

from .models import LoggedBet
from .odds import net_profit_per_unit


@dataclass
class BankrollState:
    bankroll: float = 0.0
    weekly_goal: float = 0.0
    risk_tolerance: str = "medium"
    week_anchor: str = ""          # ISO date of the current week's Monday
    bets: list[LoggedBet] = field(default_factory=list)
    _next_id: int = 1

    @staticmethod
    def _this_monday(today: date | None = None) -> str:
        today = today or date.today()
        return (today - timedelta(days=today.weekday())).isoformat()

    def ensure_week(self) -> None:
        monday = self._this_monday()
        if self.week_anchor != monday:
            self.week_anchor = monday

    def week_profit(self) -> float:
        self.ensure_week()
        anchor = date.fromisoformat(self.week_anchor)
        total = 0.0
        for b in self.bets:
            if b.result == "open":
                continue
            placed = date.fromisoformat(b.placed_on)
            if placed >= anchor:
                total += b.payout
        return total

    def days_remaining_in_week(self) -> int:
        self.ensure_week()
        anchor = date.fromisoformat(self.week_anchor)
        end = anchor + timedelta(days=6)
        today = date.today()
        return max(0, (end - today).days)

    def open_risk(self) -> float:
        return sum(b.stake for b in self.bets if b.result == "open")


# --- Persistence -------------------------------------------------------------

def load(path: str) -> BankrollState:
    if not os.path.exists(path):
        return BankrollState()
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    bets = [LoggedBet(**b) for b in raw.pop("bets", [])]
    state = BankrollState(bets=bets, **raw)
    state.ensure_week()
    return state


def save(state: BankrollState, path: str) -> None:
    data = asdict(state)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


# --- Mutations ---------------------------------------------------------------

def log_bet(
    state: BankrollState,
    *,
    game_id: str,
    market: str,
    side: str,
    american_odds: int,
    stake: float,
) -> LoggedBet:
    bet = LoggedBet(
        id=state._next_id,
        game_id=game_id,
        market=market,
        side=side,
        american_odds=american_odds,
        stake=float(stake),
        placed_on=datetime.now().date().isoformat(),
    )
    state._next_id += 1
    state.bets.append(bet)
    return bet


def settle_bet(state: BankrollState, bet_id: int, result: str) -> LoggedBet:
    if result not in {"win", "loss", "push"}:
        raise ValueError("result must be win, loss, or push")
    for b in state.bets:
        if b.id == bet_id:
            if b.result != "open":
                raise ValueError(f"bet {bet_id} already settled as {b.result}")
            b.result = result
            if result == "win":
                b.payout = round(b.stake * net_profit_per_unit(b.american_odds), 2)
                state.bankroll += b.payout
            elif result == "loss":
                b.payout = round(-b.stake, 2)
                state.bankroll += b.payout
            else:  # push
                b.payout = 0.0
            return b
    raise KeyError(f"no bet with id {bet_id}")
