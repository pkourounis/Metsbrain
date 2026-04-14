"""Turns model output + offered lines into sized, risk-classified recommendations."""

from __future__ import annotations

from . import analysis, odds
from .config import MIN_EDGE, MIN_STAKE_DOLLARS, RISK_PROFILES, risk_bucket
from .models import Game, OfferedLine, Recommendation
from .sizing import size_bet


def _model_prob_for(offered: OfferedLine, probs: dict) -> float | None:
    """Map an offered market/side onto the model's probability for that outcome."""
    m, s = offered.market, offered.side
    if m == "moneyline":
        return probs["p_win"] if s == "NYM" else 1 - probs["p_win"]
    if m == "f5_moneyline":
        return probs["p_f5_win"] if s == "NYM" else 1 - probs["p_f5_win"]
    if m == "total_over":
        return probs["p_over"]
    if m == "total_under":
        return probs["p_under"]
    if m == "run_line":
        # -1.5 run line: approximate P(Mets win by 2+) ≈ p_win^1.6
        # +1.5 run line: P(Mets don't lose by 2+) ≈ 1 - (1-p_win)^1.6
        p_win = probs["p_win"]
        if s == "NYM" and offered.line and offered.line < 0:
            return p_win ** 1.6
        if s == "NYM" and offered.line and offered.line > 0:
            return 1 - (1 - p_win) ** 1.6
        if s == "OPP" and offered.line and offered.line < 0:
            return (1 - p_win) ** 1.6
        if s == "OPP" and offered.line and offered.line > 0:
            return 1 - p_win ** 1.6
    return None


def recommend(
    games: list[Game],
    *,
    bankroll: float,
    weekly_goal: float,
    week_profit: float,
    days_remaining: int,
    risk_tolerance: str,
) -> list[Recommendation]:
    profile = RISK_PROFILES[risk_tolerance]
    allowed = profile["allow_risk_buckets"]
    min_edge = MIN_EDGE[risk_tolerance]

    out: list[Recommendation] = []

    for g in games:
        probs = analysis.evaluate(g)
        rationale = analysis.top_rationales(probs["features"])

        for line in g.offered:
            p_model = _model_prob_for(line, probs)
            if p_model is None:
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
                risk_tolerance=risk_tolerance,
                week_profit=week_profit,
                weekly_goal=weekly_goal,
                days_remaining=days_remaining,
            )
            if stake < MIN_STAKE_DOLLARS:
                continue

            out.append(Recommendation(
                game_id=g.game_id,
                market=line.market,
                side=line.side,
                american_odds=line.american_odds,
                line=line.line,
                model_prob=p_model,
                implied_prob=implied,
                edge=edge,
                kelly_full=k_full,
                stake=round(stake, 2),
                risk_bucket=bucket,
                rationale=rationale,
            ))

    # Best edge first.
    out.sort(key=lambda r: r.edge, reverse=True)
    return out
