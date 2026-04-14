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
    recent_game_score: float = 50.0
    k_per_9: float = 8.5
    expected_ip: float = 5.8
    hr_per_9: float = 1.2


@dataclass
class BatterProfile:
    """Just enough data on a Mets hitter to price their props."""
    name: str
    hr_per_pa: float                # season rate
    batting_avg: float              # season
    vs_hand_boost: float = 1.0      # multiplier vs today's opp SP handedness
    expected_pa: float = 4.1


@dataclass
class TeamForm:
    wrc_plus: int = 100
    ops_14d: float = 0.720
    bullpen_era: float = 4.00
    bullpen_rest_days: float = 1.0
    rest_days: int = 1


@dataclass
class GameContext:
    home: bool
    park_factor_runs: float = 1.00
    wind_out_rf_mph: float = 0.0
    temperature_f: float = 65.0
    injury_impact: float = 0.0


@dataclass
class OfferedLine:
    """A single market offered by the sportsbook."""
    market: str                      # moneyline / run_line / total_over / total_under /
                                     # f5_moneyline / prop_hr / prop_hits_over / prop_sp_ks_over
    side: str                        # NYM / OPP / over / under / yes / no
    american_odds: int
    line: Optional[float] = None     # run-line or total number
    player: Optional[str] = None     # for props
    threshold: Optional[float] = None  # prop threshold (e.g. 1.5 hits, 6.5 Ks)


@dataclass
class Game:
    game_id: str
    date: str                        # ISO yyyy-mm-dd
    opponent: str
    mets_pitcher: PitcherLine
    opp_pitcher: PitcherLine
    mets_form: TeamForm
    opp_form: TeamForm
    context: GameContext
    offered: list[OfferedLine] = field(default_factory=list)
    mets_lineup: list[BatterProfile] = field(default_factory=list)


@dataclass
class Recommendation:
    game_id: str
    game_date: str
    market: str
    side: str
    american_odds: int
    line: Optional[float]
    player: Optional[str]
    threshold: Optional[float]
    model_prob: float
    implied_prob: float
    edge: float
    kelly_full: float
    stake: float
    risk_bucket: str
    rationale: list[str]


@dataclass
class LoggedBet:
    id: int
    game_id: str
    market: str
    side: str
    american_odds: int
    stake: float
    placed_on: str
    result: str = "open"     # open | win | loss | push
    payout: float = 0.0
    player: Optional[str] = None
    threshold: Optional[float] = None
    line: Optional[float] = None
    recommendation_id: Optional[int] = None
    settled_at: Optional[str] = None
