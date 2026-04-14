"""Tunables. Everything the user might want to twist lives here."""

from dataclasses import dataclass


# --- Model weights -----------------------------------------------------------
# Heuristic coefficients applied to standardized feature deltas (Mets minus
# opponent, positive = good for Mets). Re-tune after backtesting.
MODEL_WEIGHTS = {
    "sp_era_diff":       0.55,   # starter ERA edge, inverted (lower is better)
    "sp_fip_diff":       0.45,
    "sp_whip_diff":      0.30,
    "sp_recent_form":    0.40,   # last-3-starts game score z-score
    "bullpen_era_diff":  0.25,
    "bullpen_rest":      0.15,
    "offense_wrcplus":   0.50,
    "offense_ops_14d":   0.35,
    "home_field":        0.18,
    "injury_penalty":    0.60,   # sign is already applied upstream
    "weather_total":     0.25,   # only affects totals model
    "rest_advantage":    0.10,
    "park_factor":       0.15,
}

# Base rates for logistic zeroing. A fully neutral game → these probabilities.
BASELINE_P_WIN = 0.50
BASELINE_P_OVER = 0.50
BASELINE_P_F5_WIN = 0.50


# --- Sizing ------------------------------------------------------------------
KELLY_FRACTION_BASE = 0.25           # quarter Kelly baseline
MAX_STAKE_PCT_OF_BANKROLL = 0.05     # hard cap per bet
MIN_STAKE_DOLLARS = 5.0              # skip plays below this after sizing

# Risk tolerance tiers.
RISK_PROFILES = {
    "low":    {"size_mult": 0.5, "allow_risk_buckets": {"low"}},
    "medium": {"size_mult": 1.0, "allow_risk_buckets": {"low", "medium"}},
    "high":   {"size_mult": 1.5, "allow_risk_buckets": {"low", "medium", "high"}},
}

# Edge thresholds — how much +EV is required before a bet is surfaced.
MIN_EDGE = {
    "low":    0.04,   # 4% edge
    "medium": 0.025,
    "high":   0.015,
}

# Risk bucket boundaries, keyed by model win probability (or appropriate prob
# for the market). A low-risk play is a strong favorite; a high-risk play is a
# coin flip or dog with a modest model edge.
def risk_bucket(p: float) -> str:
    if p >= 0.60:
        return "low"
    if p >= 0.50:
        return "medium"
    return "high"


# --- Weekly-goal pace factor ------------------------------------------------
# Multipliers on Kelly fraction based on progress toward weekly goal, bounded.
PACE_FACTOR_MIN = 0.5
PACE_FACTOR_MAX = 1.5


@dataclass
class AppPaths:
    state_file: str = ".metsbrain_state.json"
