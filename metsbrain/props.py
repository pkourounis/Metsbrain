"""Prop probability models.

Deliberately simple and transparent. Every number comes with a rationale.
"""

from __future__ import annotations

import math

from .models import BatterProfile, PitcherLine


LEAGUE_HR_PER_9 = 1.2  # rough MLB average for normalization


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# --- Home run ---------------------------------------------------------------

def p_hr(batter: BatterProfile, opp_sp: PitcherLine, park_factor: float) -> float:
    """Probability the batter hits at least one HR in expected_pa plate appearances."""
    # Scale by opposing SP HR suppression/inflation and park factor.
    sp_adj = opp_sp.hr_per_9 / LEAGUE_HR_PER_9
    per_pa = batter.hr_per_pa * batter.vs_hand_boost * sp_adj * park_factor
    per_pa = _clamp(per_pa, 0.001, 0.30)
    return 1 - (1 - per_pa) ** batter.expected_pa


def hr_rationale(batter: BatterProfile, opp_sp: PitcherLine, park_factor: float) -> list[str]:
    return [
        f"{batter.name} HR/PA {batter.hr_per_pa:.3f} (boost x{batter.vs_hand_boost:.2f})",
        f"Opp SP {opp_sp.name} HR/9 {opp_sp.hr_per_9:.2f}",
        f"Park factor {park_factor:.2f}",
    ]


# --- Hits over N ------------------------------------------------------------

def _binom_p_at_least(n: int, k: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    cdf = 0.0
    for i in range(k):
        cdf += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return 1 - cdf


def p_hits_over(batter: BatterProfile, opp_sp: PitcherLine, threshold: float) -> float:
    """Prob batter gets strictly more than `threshold` hits.

    Thresholds are .5-ended (0.5 => need >=1 hit, 1.5 => need >=2)."""
    # Adjust BA by opposing SP quality (proxied by ERA vs league ~4.00).
    sp_quality = _clamp(opp_sp.era / 4.00, 0.75, 1.25)
    eff_ba = _clamp(batter.batting_avg * batter.vs_hand_boost * sp_quality, 0.15, 0.45)
    abs_per_game = 4  # approximate official at-bats (excludes BB/HBP)
    target = int(threshold + 0.5)
    return _binom_p_at_least(abs_per_game, target, eff_ba)


def hits_rationale(batter: BatterProfile, opp_sp: PitcherLine, threshold: float) -> list[str]:
    return [
        f"{batter.name} BA {batter.batting_avg:.3f} (boost x{batter.vs_hand_boost:.2f})",
        f"Opp SP {opp_sp.name} ERA {opp_sp.era:.2f}",
        f"Threshold {threshold} hits",
    ]


# --- SP strikeouts over N ---------------------------------------------------

def _poisson_p_at_least(lam: float, k: int) -> float:
    """P(X >= k) for X ~ Poisson(lam)."""
    cdf = 0.0
    for i in range(k):
        cdf += (lam ** i) * math.exp(-lam) / math.factorial(i)
    return 1 - cdf


def p_sp_ks_over(sp: PitcherLine, threshold: float) -> float:
    """Prob SP records strictly more than `threshold` strikeouts."""
    lam = sp.k_per_9 * sp.expected_ip / 9.0
    target = int(threshold + 0.5)
    return _poisson_p_at_least(lam, target)


def sp_ks_rationale(sp: PitcherLine, threshold: float) -> list[str]:
    exp_k = sp.k_per_9 * sp.expected_ip / 9.0
    return [
        f"{sp.name} K/9 {sp.k_per_9:.1f} over {sp.expected_ip:.1f} IP",
        f"Expected Ks ~{exp_k:.1f}",
        f"Threshold {threshold} Ks",
    ]
