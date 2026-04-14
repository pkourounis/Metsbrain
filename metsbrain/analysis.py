"""Mets-specific win-probability + totals model (heuristic logistic)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import (
    BASELINE_P_F5_WIN,
    BASELINE_P_OVER,
    BASELINE_P_WIN,
    MODEL_WEIGHTS,
)
from .models import Game


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


@dataclass
class FeatureContribution:
    name: str
    value: float
    weighted: float
    note: str

    def to_dict(self) -> dict:
        return {"name": self.name, "value": self.value,
                "weighted": self.weighted, "note": self.note}


def _extract(game: Game) -> list[FeatureContribution]:
    m = game.mets_pitcher
    o = game.opp_pitcher
    mf = game.mets_form
    of = game.opp_form
    ctx = game.context
    w = MODEL_WEIGHTS

    feats: list[FeatureContribution] = []

    era_delta = (o.era - m.era) / 1.5
    feats.append(FeatureContribution(
        "sp_era_diff", era_delta, era_delta * w["sp_era_diff"],
        f"{m.name} ERA {m.era:.2f} vs {o.name} {o.era:.2f}",
    ))
    fip_delta = (o.fip - m.fip) / 1.5
    feats.append(FeatureContribution(
        "sp_fip_diff", fip_delta, fip_delta * w["sp_fip_diff"],
        f"FIP {m.fip:.2f} vs {o.fip:.2f}",
    ))
    whip_delta = (o.whip - m.whip) / 0.25
    feats.append(FeatureContribution(
        "sp_whip_diff", whip_delta, whip_delta * w["sp_whip_diff"],
        f"WHIP {m.whip:.2f} vs {o.whip:.2f}",
    ))
    form_delta = (m.recent_game_score - o.recent_game_score) / 15.0
    feats.append(FeatureContribution(
        "sp_recent_form", form_delta, form_delta * w["sp_recent_form"],
        f"Recent game-score {m.recent_game_score:.0f} vs {o.recent_game_score:.0f}",
    ))

    pen_delta = (of.bullpen_era - mf.bullpen_era) / 1.0
    feats.append(FeatureContribution(
        "bullpen_era_diff", pen_delta, pen_delta * w["bullpen_era_diff"],
        f"Bullpen ERA {mf.bullpen_era:.2f} vs {of.bullpen_era:.2f}",
    ))
    rest_delta = (mf.bullpen_rest_days - of.bullpen_rest_days) / 1.0
    feats.append(FeatureContribution(
        "bullpen_rest", rest_delta, rest_delta * w["bullpen_rest"],
        f"Bullpen rest {mf.bullpen_rest_days:.1f}d vs {of.bullpen_rest_days:.1f}d",
    ))

    wrc_delta = (mf.wrc_plus - of.wrc_plus) / 20.0
    feats.append(FeatureContribution(
        "offense_wrcplus", wrc_delta, wrc_delta * w["offense_wrcplus"],
        f"wRC+ {mf.wrc_plus} vs {of.wrc_plus}",
    ))
    ops_delta = (mf.ops_14d - of.ops_14d) / 0.080
    feats.append(FeatureContribution(
        "offense_ops_14d", ops_delta, ops_delta * w["offense_ops_14d"],
        f"14d OPS {mf.ops_14d:.3f} vs {of.ops_14d:.3f}",
    ))

    hfa = 1.0 if ctx.home else -1.0
    feats.append(FeatureContribution(
        "home_field", hfa, hfa * w["home_field"],
        "Home at Citi Field" if ctx.home else "On the road",
    ))

    feats.append(FeatureContribution(
        "injury_penalty", ctx.injury_impact, ctx.injury_impact * w["injury_penalty"],
        f"Injury impact {ctx.injury_impact:+.2f}",
    ))

    rest = (mf.rest_days - of.rest_days) / 2.0
    feats.append(FeatureContribution(
        "rest_advantage", rest, rest * w["rest_advantage"],
        f"Team rest {mf.rest_days}d vs {of.rest_days}d",
    ))

    return feats


def evaluate(game: Game) -> dict:
    feats = _extract(game)

    logit_base_win = _logit(BASELINE_P_WIN) + sum(f.weighted for f in feats)
    p_win = _sigmoid(logit_base_win)

    f5_weights = {"sp_era_diff", "sp_fip_diff", "sp_whip_diff",
                  "sp_recent_form", "home_field", "injury_penalty"}
    logit_base_f5 = _logit(BASELINE_P_F5_WIN) + sum(
        f.weighted for f in feats if f.name in f5_weights
    )
    p_f5_win = _sigmoid(logit_base_f5)

    ctx = game.context
    offense_push = 0.0
    for f in feats:
        if f.name in {"offense_wrcplus", "offense_ops_14d"}:
            offense_push += abs(f.weighted) * 0.3
    pitching_drag = 0.0
    for f in feats:
        if f.name in {"sp_era_diff", "sp_fip_diff", "bullpen_era_diff"}:
            pitching_drag += -abs(f.weighted) * 0.2
    weather_push = (
        max(0.0, ctx.wind_out_rf_mph - 5.0) / 10.0
        + max(0.0, ctx.temperature_f - 70.0) / 30.0
    ) * MODEL_WEIGHTS["weather_total"]
    park_push = (ctx.park_factor_runs - 1.0) * MODEL_WEIGHTS["park_factor"]
    logit_base_over = (
        _logit(BASELINE_P_OVER)
        + offense_push
        + pitching_drag
        + weather_push
        + park_push
    )
    p_over = _sigmoid(logit_base_over)

    return {
        "p_win": p_win,
        "p_f5_win": p_f5_win,
        "p_over": p_over,
        "p_under": 1 - p_over,
        "features": feats,
    }


def top_rationales(features: list[FeatureContribution], k: int = 3) -> list[str]:
    ordered = sorted(features, key=lambda f: abs(f.weighted), reverse=True)
    out = []
    for f in ordered[:k]:
        direction = "+" if f.weighted >= 0 else "-"
        out.append(f"[{direction}{abs(f.weighted):.2f}] {f.note}")
    return out
