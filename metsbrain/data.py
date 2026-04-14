"""Data provider abstraction + a bundled sample week of Mets games.

Real sources (MLB Stats API, pybaseball, Open-Meteo) arrive in Phase 3. Until
then, SampleDataProvider gives us realistic-looking games + prop lines so the
full pipeline is exercisable offline.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol

from .models import (
    BatterProfile,
    Game,
    GameContext,
    OfferedLine,
    PitcherLine,
    TeamForm,
)


class DataProvider(Protocol):
    def upcoming_games(self) -> list[Game]: ...


# --- Sample lineup / pitcher defaults ---------------------------------------

_SAMPLE_METS_LINEUP = [
    BatterProfile("Lindor", hr_per_pa=0.042, batting_avg=0.265, vs_hand_boost=1.05),
    BatterProfile("Alonso", hr_per_pa=0.050, batting_avg=0.250, vs_hand_boost=1.10),
    BatterProfile("Nimmo",  hr_per_pa=0.030, batting_avg=0.275, vs_hand_boost=1.00),
]


class SampleDataProvider:
    """A realistic-looking week of Mets games + offered prop lines."""

    def upcoming_games(self) -> list[Game]:
        today = date.today()
        d = lambda n: (today + timedelta(days=n)).isoformat()

        return [
            Game(
                game_id=f"NYM-vs-MIA-{d(1)}",
                date=d(1),
                opponent="MIA",
                mets_pitcher=PitcherLine("Senga",  era=3.10, fip=3.35, whip=1.12,
                                         recent_game_score=62, k_per_9=10.8,
                                         expected_ip=6.0, hr_per_9=0.90),
                opp_pitcher=PitcherLine("Perez",   era=4.85, fip=4.60, whip=1.40,
                                         recent_game_score=44, k_per_9=7.2,
                                         expected_ip=5.2, hr_per_9=1.45),
                mets_form=TeamForm(wrc_plus=112, ops_14d=0.760, bullpen_era=3.40,
                                   bullpen_rest_days=1.2, rest_days=1),
                opp_form =TeamForm(wrc_plus= 88, ops_14d=0.680, bullpen_era=4.60,
                                   bullpen_rest_days=0.6, rest_days=1),
                context=GameContext(home=True, park_factor_runs=0.97,
                                    wind_out_rf_mph=3, temperature_f=68,
                                    injury_impact=0.1),
                mets_lineup=_SAMPLE_METS_LINEUP,
                offered=[
                    OfferedLine("moneyline",       "NYM",   -175),
                    OfferedLine("moneyline",       "OPP",   +150),
                    OfferedLine("run_line",        "NYM",   -120, line=-1.5),
                    OfferedLine("run_line",        "OPP",   +100, line=+1.5),
                    OfferedLine("total_over",      "over",  -110, line=8.5),
                    OfferedLine("total_under",     "under", -110, line=8.5),
                    OfferedLine("f5_moneyline",    "NYM",   -140),
                    OfferedLine("f5_moneyline",    "OPP",   +120),
                    OfferedLine("prop_hr",         "yes",   +340, player="Alonso"),
                    OfferedLine("prop_hr",         "yes",   +420, player="Lindor"),
                    OfferedLine("prop_hits_over",  "over",  -155, player="Nimmo", threshold=0.5),
                    OfferedLine("prop_sp_ks_over", "over",  -120, threshold=6.5),
                ],
            ),
            Game(
                game_id=f"NYM-vs-PHI-{d(2)}",
                date=d(2),
                opponent="PHI",
                mets_pitcher=PitcherLine("Manaea",  era=3.85, fip=4.00, whip=1.28,
                                         recent_game_score=48, k_per_9=9.1,
                                         expected_ip=5.6, hr_per_9=1.25),
                opp_pitcher=PitcherLine("Wheeler",  era=2.75, fip=2.90, whip=1.00,
                                         recent_game_score=68, k_per_9=10.2,
                                         expected_ip=6.5, hr_per_9=0.95),
                mets_form=TeamForm(wrc_plus=112, ops_14d=0.760, bullpen_era=3.40,
                                   bullpen_rest_days=0.8, rest_days=0),
                opp_form =TeamForm(wrc_plus=118, ops_14d=0.795, bullpen_era=3.10,
                                   bullpen_rest_days=1.5, rest_days=1),
                context=GameContext(home=False, park_factor_runs=1.05,
                                    wind_out_rf_mph=8, temperature_f=74,
                                    injury_impact=-0.1),
                mets_lineup=_SAMPLE_METS_LINEUP,
                offered=[
                    OfferedLine("moneyline",   "NYM", +165),
                    OfferedLine("moneyline",   "OPP", -190),
                    OfferedLine("run_line",    "NYM", -115, line=+1.5),
                    OfferedLine("run_line",    "OPP", -105, line=-1.5),
                    OfferedLine("total_over",  "over",  -105, line=8.5),
                    OfferedLine("total_under", "under", -115, line=8.5),
                    OfferedLine("prop_hr",            "yes",  +360, player="Alonso"),
                    OfferedLine("prop_hits_over",     "over", +110, player="Lindor", threshold=1.5),
                    OfferedLine("prop_sp_ks_over",    "over", -110, threshold=5.5),
                ],
            ),
            Game(
                game_id=f"NYM-vs-ATL-{d(3)}",
                date=d(3),
                opponent="ATL",
                mets_pitcher=PitcherLine("Megill",   era=3.95, fip=4.10, whip=1.25,
                                         recent_game_score=55, k_per_9=8.6,
                                         expected_ip=5.5, hr_per_9=1.30),
                opp_pitcher=PitcherLine("Sale",      era=3.20, fip=3.35, whip=1.10,
                                         recent_game_score=60, k_per_9=11.5,
                                         expected_ip=6.2, hr_per_9=1.05),
                mets_form=TeamForm(wrc_plus=112, ops_14d=0.760, bullpen_era=3.40,
                                   bullpen_rest_days=1.0, rest_days=1),
                opp_form =TeamForm(wrc_plus=120, ops_14d=0.800, bullpen_era=3.60,
                                   bullpen_rest_days=1.0, rest_days=1),
                context=GameContext(home=True, park_factor_runs=0.97,
                                    wind_out_rf_mph=2, temperature_f=62,
                                    injury_impact=0.0),
                mets_lineup=_SAMPLE_METS_LINEUP,
                offered=[
                    OfferedLine("moneyline",     "NYM", +125),
                    OfferedLine("moneyline",     "OPP", -145),
                    OfferedLine("total_over",    "over",  -110, line=7.5),
                    OfferedLine("total_under",   "under", -110, line=7.5),
                    OfferedLine("f5_moneyline",  "NYM", +115),
                    OfferedLine("f5_moneyline",  "OPP", -135),
                    OfferedLine("prop_hr",       "yes",  +450, player="Nimmo"),
                    OfferedLine("prop_sp_ks_over","over", +100, threshold=5.5),
                ],
            ),
        ]
