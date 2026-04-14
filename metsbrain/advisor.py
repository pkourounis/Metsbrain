"""Turns model output + offered lines into sized, risk-classified, rule-checked recommendations."""

from __future__ import annotations

from collections import defaultdict

from . import analysis, odds, props
from .config import (
    MAX_BETS_PER_DAY,
    MAX_STAKE_PCT_PER_GAME,
    MIN_EDGE,
    MIN_STAKE_DOLLARS,
    RISK_PROFILES,
    WEEKLY_DRAWDOWN_COOLDOWN_PCT,
    risk_bucket,
)
from .models import Game, OfferedLine, Recommendation
from .sizing import size_bet


# --- Market → model probability mapping --------------------------------------

def _model_prob_for(offered: OfferedLine, probs: dict, game: Game) -> tuple[float | None, list[str]]:
    """Return (probability for this offered side, market-specific rationale)."""
    m, s = offered.market, offered.side

    if m == "moneyline":
        p = probs["p_win"] if s == "NYM" else 1 - probs["p_win"]
        return p, []

    if m == "f5_moneyline":
        p = probs["p_f5_win"] if s == "NYM" else 1 - probs["p_f5_win"]
        return p, []

    if m == "total_over":
        return probs["p_over"], []
    if m == "total_under":
        return probs["p_under"], []

    if m == "run_line":
        p_win = probs["p_win"]
        if offered.line is None:
            return None, []
        if s == "NYM" and offered.line < 0:
            return p_win ** 1.6, []
        if s == "NYM" and offered.line > 0:
            return 1 - (1 - p_win) ** 1.6, []
        if s == "OPP" and offered.line < 0:
            return (1 - p_win) ** 1.6, []
        if s == "OPP" and offered.line > 0:
            return 1 - p_win ** 1.6, []
        return None, []

    if m == "prop_hr":
        batter = next((b for b in game.mets_lineup if b.name == offered.player), None)
        if batter is None:
            return None, []
        p = props.p_hr(batter, game.opp_pitcher, game.context.park_factor_runs)
        rat = props.hr_rationale(batter, game.opp_pitcher, game.context.park_factor_runs)
        return (p if s == "yes" else 1 - p), rat

    if m == "prop_hits_over":
        batter = next((b for b in game.mets_lineup if b.name == offered.player), None)
        if batter is None or offered.threshold is None:
            return None, []
        p = props.p_hits_over(batter, game.opp_pitcher, offered.threshold)
        rat = props.hits_rationale(batter, game.opp_pitcher, offered.threshold)
        return (p if s == "over" else 1 - p), rat

    if m == "prop_sp_ks_over":
        if offered.threshold is None:
            return None, []
        p = props.p_sp_ks_over(game.mets_pitcher, offered.threshold)
        rat = props.sp_ks_rationale(game.mets_pitcher, offered.threshold)
        return (p if s == "over" else 1 - p), rat

    return None, []


# --- Per-game recommendation assembly ---------------------------------------

def _recs_for_game(
    game: Game,
    *,
    bankroll: float,
    weekly_goal: float,
    week_profit: float,
    days_remaining: int,
    effective_risk: str,
    pace_override: float | None,
    locked_down: bool,
) -> list[Recommendation]:
    profile = RISK_PROFILES[effective_risk]
    allowed = profile["allow_risk_buckets"]
    min_prob = profile["min_model_prob"]
    min_edge = MIN_EDGE[effective_risk]

    probs = analysis.evaluate(game)
    game_rationale = analysis.top_rationales(probs["features"])

    candidates: list[Recommendation] = []

    for line in game.offered:
        p_model, market_rat = _model_prob_for(line, probs, game)
        if p_model is None:
            continue
        if p_model < min_prob:
            continue

        implied = odds.american_to_implied(line.american_odds)
        edge = p_model - implied
        if edge < min_edge:
            continue

        bucket = risk_bucket(p_model)
        if bucket not in allowed:
            continue

        k_full = odds.kelly_fraction(p_model, line.american_odds)
        stake = size_bet(
            kelly_full=k_full,
            bankroll=bankroll,
            risk_tolerance=effective_risk,
            week_profit=week_profit,
            weekly_goal=weekly_goal,
            days_remaining=days_remaining,
            pace_factor_override=pace_override,
        )
        if stake < MIN_STAKE_DOLLARS:
            continue

        rat = market_rat if market_rat else game_rationale
        if locked_down:
            rat = ["[goal hit — low-risk lockdown]"] + rat

        candidates.append(Recommendation(
            game_id=game.game_id,
            game_date=game.date,
            market=line.market,
            side=line.side,
            american_odds=line.american_odds,
            line=line.line,
            player=line.player,
            threshold=line.threshold,
            model_prob=p_model,
            implied_prob=implied,
            edge=edge,
            kelly_full=k_full,
            stake=round(stake, 2),
            risk_bucket=bucket,
            rationale=rat,
        ))

    # Correlation cap: all picks on a game scaled down to fit MAX_STAKE_PCT_PER_GAME.
    cap = MAX_STAKE_PCT_PER_GAME * bankroll
    total = sum(r.stake for r in candidates)
    if total > cap and total > 0:
        scale = cap / total
        for r in candidates:
            r.stake = round(r.stake * scale, 2)
        candidates = [r for r in candidates if r.stake >= MIN_STAKE_DOLLARS]

    return candidates


# --- Top-level entry point ---------------------------------------------------

def recommend(
    games: list[Game],
    *,
    bankroll: float,
    starting_bankroll_this_week: float,
    weekly_goal: float,
    week_profit: float,
    days_remaining: int,
    risk_tolerance: str,
) -> list[Recommendation]:
    # Drawdown cool-down: refuse new picks if the week has been brutal.
    if starting_bankroll_this_week > 0:
        drawdown = (starting_bankroll_this_week - bankroll) / starting_bankroll_this_week
        if drawdown > WEEKLY_DRAWDOWN_COOLDOWN_PCT:
            return []

    # Goal-hit lockdown: flip to low-risk-only and halve the pace factor.
    locked_down = weekly_goal > 0 and week_profit >= weekly_goal
    effective_risk = "low" if locked_down else risk_tolerance
    pace_override = 0.5 if locked_down else None

    all_recs: list[Recommendation] = []
    for g in games:
        all_recs.extend(_recs_for_game(
            g,
            bankroll=bankroll,
            weekly_goal=weekly_goal,
            week_profit=week_profit,
            days_remaining=days_remaining,
            effective_risk=effective_risk,
            pace_override=pace_override,
            locked_down=locked_down,
        ))

    # Rank by edge and apply the max-3-per-day cap.
    all_recs.sort(key=lambda r: r.edge, reverse=True)
    per_day: dict[str, int] = defaultdict(int)
    capped: list[Recommendation] = []
    for r in all_recs:
        if per_day[r.game_date] >= MAX_BETS_PER_DAY:
            continue
        per_day[r.game_date] += 1
        capped.append(r)

    return capped
