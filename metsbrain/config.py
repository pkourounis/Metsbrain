"""Tunables. Everything the user might want to twist lives here."""

from dataclasses import dataclass


# --- Model weights -----------------------------------------------------------
# Heuristic coefficients applied to standardized feature deltas (Mets minus
# opponent, positive = good for Mets). Re-tune after backtesting.
MODEL_WEIGHTS = {
    "sp_era_diff":       0.55,
    "sp_fip_diff":       0.45,
    "sp_whip_diff":      0.30,
    "sp_recent_form":    0.40,
    "bullpen_era_diff":  0.25,
    "bullpen_rest":      0.15,
    "offense_wrcplus":   0.50,
    "offense_ops_14d":   0.35,
    "home_field":        0.18,
    "injury_penalty":    0.60,
    "weather_total":     0.25,
    "rest_advantage":    0.10,
    "park_factor":       0.15,
}

BASELINE_P_WIN = 0.50
BASELINE_P_OVER = 0.50
BASELINE_P_F5_WIN = 0.50


# --- Sizing ------------------------------------------------------------------
KELLY_FRACTION_BASE = 0.25           # quarter Kelly baseline
MAX_STAKE_PCT_OF_BANKROLL = 0.05     # hard cap per bet
MAX_STAKE_PCT_PER_GAME = 0.07        # correlation cap: all bets on a game
MIN_STAKE_DOLLARS = 5.0              # skip plays below this after sizing

# Risk tolerance tiers.
RISK_PROFILES = {
    "low":    {"size_mult": 0.5, "allow_risk_buckets": {"low"},                     "min_model_prob": 0.60},
    "medium": {"size_mult": 1.0, "allow_risk_buckets": {"low", "medium"},           "min_model_prob": 0.50},
    "high":   {"size_mult": 1.5, "allow_risk_buckets": {"low", "medium", "high"},   "min_model_prob": 0.45},
}

# Minimum model-vs-implied edge required before a pick surfaces.
MIN_EDGE = {
    "low":    0.04,
    "medium": 0.025,
    "high":   0.015,
}


def risk_bucket(p: float) -> str:
    if p >= 0.60:
        return "low"
    if p >= 0.50:
        return "medium"
    return "high"


# --- Weekly-goal pace factor + safety rules ---------------------------------
PACE_FACTOR_MIN = 0.5
PACE_FACTOR_MAX = 1.5

# Hard daily cap on how many picks the advisor will surface.
MAX_BETS_PER_DAY = 3

# Safety: refuse new picks once weekly drawdown from starting bankroll exceeds
# this fraction. Forces a cool-down until next Monday.
WEEKLY_DRAWDOWN_COOLDOWN_PCT = 0.25


@dataclass
class AppPaths:
    db_file: str = ".metsbrain.db"
