import math

from metsbrain.models import BatterProfile, PitcherLine
from metsbrain.props import p_hits_over, p_hr, p_sp_ks_over


def _batter(**kw):
    defaults = dict(name="X", hr_per_pa=0.03, batting_avg=0.260)
    defaults.update(kw)
    return BatterProfile(**defaults)


def _pitcher(**kw):
    defaults = dict(name="P", era=4.00, fip=4.00, whip=1.30)
    defaults.update(kw)
    return PitcherLine(**defaults)


def test_p_hr_is_between_zero_and_one():
    p = p_hr(_batter(hr_per_pa=0.05), _pitcher(hr_per_9=1.5), park_factor=1.05)
    assert 0.0 < p < 1.0


def test_p_hr_scales_with_opp_sp_hr_allowed():
    low = p_hr(_batter(), _pitcher(hr_per_9=0.6), park_factor=1.0)
    high = p_hr(_batter(), _pitcher(hr_per_9=1.8), park_factor=1.0)
    assert high > low


def test_p_hits_over_half_greater_than_over_one_and_a_half():
    b = _batter(batting_avg=0.280)
    sp = _pitcher(era=4.50)
    p_half = p_hits_over(b, sp, 0.5)
    p_one_five = p_hits_over(b, sp, 1.5)
    assert p_half > p_one_five
    assert 0.0 < p_one_five < p_half < 1.0


def test_p_hits_over_lower_vs_tough_pitcher():
    b = _batter(batting_avg=0.280)
    easy = p_hits_over(b, _pitcher(era=5.50), 0.5)
    tough = p_hits_over(b, _pitcher(era=2.50), 0.5)
    assert easy > tough


def test_p_sp_ks_over_scales_with_k_per_9():
    low_k = p_sp_ks_over(_pitcher(k_per_9=6.0, expected_ip=6.0), 6.5)
    high_k = p_sp_ks_over(_pitcher(k_per_9=11.0, expected_ip=6.0), 6.5)
    assert high_k > low_k


def test_p_sp_ks_over_bounded():
    p = p_sp_ks_over(_pitcher(k_per_9=9.0, expected_ip=6.0), 6.5)
    assert 0.0 < p < 1.0
    # And a very high threshold should be tiny.
    p_impossible = p_sp_ks_over(_pitcher(k_per_9=9.0, expected_ip=6.0), 99.5)
    assert math.isclose(p_impossible, 0.0, abs_tol=1e-6)
