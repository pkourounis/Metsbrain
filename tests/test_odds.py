import math

from metsbrain.odds import (
    american_to_decimal,
    american_to_implied,
    devig_two_way,
    kelly_fraction,
    net_profit_per_unit,
)


def test_american_to_decimal_positive():
    assert math.isclose(american_to_decimal(+150), 2.5)


def test_american_to_decimal_negative():
    assert math.isclose(american_to_decimal(-200), 1.5)


def test_implied_prob_symmetry():
    assert math.isclose(american_to_implied(-200), 2 / 3, rel_tol=1e-9)
    assert math.isclose(american_to_implied(+100), 0.5, rel_tol=1e-9)


def test_devig_two_way_sums_to_one():
    a, b = devig_two_way(-110, -110)
    assert math.isclose(a + b, 1.0)
    assert math.isclose(a, 0.5)


def test_net_profit_per_unit():
    assert math.isclose(net_profit_per_unit(+150), 1.5)
    assert math.isclose(net_profit_per_unit(-200), 0.5)


def test_kelly_fraction_zero_on_no_edge():
    # Fair odds for 50%: +100. Zero edge → zero Kelly.
    assert kelly_fraction(0.5, +100) == 0.0


def test_kelly_fraction_positive_on_edge():
    # 60% on +100 → Kelly = (1*0.6 - 0.4)/1 = 0.2
    assert math.isclose(kelly_fraction(0.6, +100), 0.2)


def test_kelly_fraction_clamped_below_zero():
    assert kelly_fraction(0.3, +100) == 0.0
