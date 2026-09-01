"""Merit-order clearing: prices, partial dispatch, ties, scarcity, two-sided."""

import pytest
from market.engine.clearing import Bid, clear
from market.engine.tech import VOLL


def sell(price, qty, team="t", key="k", cost=0.0):
    return Bid(team, key, price, qty, cost, "sell")


def buy(price, qty, team="t", key="k"):
    return Bid(team, key, price, qty, 0.0, "buy")


def cleared(res, team=None):
    return {(a.team, a.key, a.side): a.cleared for a in res.awards}


def test_marginal_offer_sets_price():
    res = clear([sell(20, 100, "a"), sell(40, 100, "b")], demand=150)
    assert res.price == 40
    assert res.volume == pytest.approx(150)
    assert cleared(res)[("a", "k", "sell")] == pytest.approx(100)
    assert cleared(res)[("b", "k", "sell")] == pytest.approx(50)  # partial marginal


def test_bid_between_price_levels_partially_dispatched():
    res = clear([sell(20, 60, "a"), sell(50, 100, "b")], demand=100)
    assert res.price == 50
    assert cleared(res)[("b", "k", "sell")] == pytest.approx(40)


def test_tie_at_marginal_price_split_pro_rata():
    res = clear([sell(30, 100, "a"), sell(30, 100, "b")], demand=100)
    assert res.price == 30
    assert cleared(res)[("a", "k", "sell")] == pytest.approx(50)
    assert cleared(res)[("b", "k", "sell")] == pytest.approx(50)


def test_demand_on_level_boundary_sets_that_price():
    res = clear([sell(20, 100, "a"), sell(40, 100, "b")], demand=100)
    assert res.price == 20
    assert cleared(res)[("b", "k", "sell")] == pytest.approx(0)


def test_abundant_zero_cost_renewables_set_price_zero():
    res = clear([sell(0, 500, "wind")], demand=300)
    assert res.price == 0
    assert res.volume == pytest.approx(300)


def test_scarcity_sheds_load_at_voll():
    res = clear([sell(20, 100, "a")], demand=150)
    assert res.price == VOLL  # load shedding pays the value of lost load
    assert res.scarce
    assert res.served == pytest.approx(100)
    assert res.unserved == pytest.approx(50)
    assert cleared(res)[("a", "k", "sell")] == pytest.approx(100)


def test_no_bids_all_unserved():
    res = clear([], demand=100)
    assert res.unserved == pytest.approx(100)
    assert res.volume == 0


def test_charging_buys_when_cheap_not_when_expensive():
    # base demand 100, plenty of 30 EUR supply; two chargers willing to pay 25 and 60
    res = clear(
        [sell(30, 400, "gen"), buy(25, 100, "cheap"), buy(60, 100, "rich")],
        demand=100,
    )
    assert res.price == 30
    c = cleared(res)
    assert c[("rich", "k", "buy")] == pytest.approx(100)  # willing to pay 60 >= 30
    assert c[("cheap", "k", "buy")] == pytest.approx(0)  # only willing 25 < 30
    # supply covers base demand + accepted charging = 200
    assert res.volume == pytest.approx(200)
    assert c[("gen", "k", "sell")] == pytest.approx(200)


def test_no_charging_during_scarcity():
    res = clear([sell(20, 100, "gen"), buy(180, 50, "charger")], demand=150)
    assert res.scarce
    c = cleared(res)
    assert c[("charger", "k", "buy")] == pytest.approx(0)
    assert c[("gen", "k", "sell")] == pytest.approx(100)


def test_all_bids_at_cap_clear_at_cap_and_are_not_scarce():
    # if every offer sits at the ceiling, that is the price - supply still meets demand
    res = clear([sell(VOLL, 200, "a")], demand=100)
    assert res.price == VOLL
    assert not res.scarce
    assert cleared(res)[("a", "k", "sell")] == pytest.approx(100)


def test_negative_offers_produce_a_negative_clearing_price():
    # oversupply with the marginal offer below zero pushes the price negative
    res = clear([sell(-100, 200, "a")], demand=50)
    assert res.price == -100
    assert cleared(res)[("a", "k", "sell")] == pytest.approx(50)


def test_offer_above_clearing_price_is_not_dispatched():
    res = clear([sell(20, 100, "cheap"), sell(90, 100, "dear")], demand=100)
    assert res.price == 20
    assert cleared(res)[("dear", "k", "sell")] == pytest.approx(0)
