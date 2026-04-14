"""Core dataclasses used across the app."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PitcherLine:
    name: str
    era: float
    fip: float
    whip: float
    # Mean game score of last 3 starts (50 = average, higher = better).
    recent_game_score: float = 50.0


@dataclass
class TeamForm:
    wrc_plus: int = 100             # 100 = league average
    ops_14d: float = 0.720
    bullpen_era: float = 4.00
    bullpen_rest_days: float = 1.0  # avg rest for top-3 relievers
    rest_days: int = 1              # team rest days since last game


@dataclass
class GameContext:
    home: bool
    park_factor_runs: float = 1.00  # 1.00 = neutral; Citi plays pitcher-friendly
    wind_out_rf_mph: float = 0.0
    temperature_f: float = 65.0
    injury_impact: float = 0.0      # -1 (Mets decimated) .. +1 (opponent decimated)


@dataclass
class OfferedLine:
    """A single market offered by the sportsbook."""
    market: str          # e.g. "moneyline", "run_line", "total_over", "total_under", "f5_moneyline"
    side: str            # "NYM", "OPP", "over", "under"
    american_odds: int   # e.g. -120, +145
    line: Optional[float] = None  # run line / total number, if applicable


@dataclass
class Game:
    game_id: str                 # e.g. "NYM-vs-PHI-2026-04-15"
    date: str                    # ISO yyyy-mm-dd
    opponent: str
    mets_pitcher: PitcherLine
    opp_pitcher: PitcherLine
    mets_form: TeamForm
    opp_form: TeamForm
    context: GameContext
    offered: list[OfferedLine] = field(default_factory=list)


@dataclass
class Recommendation:
    game_id: str
    market: str
    side: str
    american_odds: int
    line: Optional[float]
    model_prob: float
    implied_prob: float
    edge: float                  # model_prob - implied_prob
    kelly_full: float            # 0..1 full-Kelly fraction
    stake: float                 # dollars, already risk- and pace-adjusted
    risk_bucket: str             # "low" | "medium" | "high"
    rationale: list[str]         # human-readable reasons driving the pick


@dataclass
class LoggedBet:
    id: int
    game_id: str
    market: str
    side: str
    american_odds: int
    stake: float
    placed_on: str      # ISO date
    result: str = "open"  # open | win | loss | push
    payout: float = 0.0   # net profit; negative on loss
