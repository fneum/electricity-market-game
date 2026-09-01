"""Game layer: assignment/scaling, validation, profits, storage across rounds."""

import random

import pytest
from market.engine.game import BidError, Game, Segment, Team, assign_techs
from market.engine.scenario import PRESETS
from market.engine.tech import TECHS


def new_game(n, preset="classic"):
    g = Game(scenarios=list(PRESETS[preset]))
    g.teams = [Team(f"T{i}", "", 1.0, 0.0) for i in range(n)]
    g.start(random.Random(0))
    return g


def team_with(g, key):
    return next(t for t in g.teams if t.tech == key)


def test_assignment_preserves_capacity_when_split():
    picks = assign_techs(14, random.Random(1))
    counts = {k: picks.count(k) for k in set(picks)}
    for k, n in counts.items():
        assert n * (TECHS[k].capacity / n) == pytest.approx(TECHS[k].capacity)
    assert len(picks) == 14


def test_all_techs_covered_when_enough_teams():
    picks = assign_techs(7, random.Random(2))
    assert set(picks) == set(TECHS)


def test_start_needs_two_teams():
    g = Game(scenarios=list(PRESETS["classic"]))
    g.teams = [Team("solo", "", 1.0, 0.0)]
    with pytest.raises(BidError):
        g.start(random.Random(0))


def test_variable_capacity_scaled_by_weather():
    g = new_game(7)
    g.open_round()  # 06:00, onshore availability 0.20
    wind = team_with(g, "onshore")
    cap = g.sell_capacity(wind, g.scenario)
    assert cap == pytest.approx(TECHS["onshore"].capacity * wind.share * 0.20)


def test_bid_over_capacity_rejected():
    g = new_game(7)
    g.open_round()
    coal = team_with(g, "coal")
    limit = g.sell_capacity(coal, g.scenario)
    with pytest.raises(BidError):
        g.submit(coal, [Segment(40, limit + 10)])


def test_price_out_of_range_rejected():
    g = new_game(7)
    g.open_round()
    coal = team_with(g, "coal")
    with pytest.raises(BidError):
        g.submit(coal, [Segment(5000, 100)])  # above the cap (value of lost load)
    with pytest.raises(BidError):
        g.submit(coal, [Segment(-1000, 100)])  # below the floor


def test_negative_bid_allowed():
    g = new_game(7)
    g.open_round()
    wind = team_with(g, "onshore")
    cap = g.sell_capacity(wind, g.scenario)
    g.submit(wind, [Segment(-50, cap)])  # bidding negative to avoid being switched off
    assert wind.submitted


def test_only_storage_can_charge():
    g = new_game(7)
    g.open_round()
    coal = team_with(g, "coal")
    with pytest.raises(BidError):
        g.submit(coal, [Segment(10, 50, side="buy")])


def test_profit_paid_at_clearing_price():
    g = new_game(7)
    g.open_round()  # demand 3000; cheap hydro + renewables clear at 20
    for t in g.teams:
        cap = g.sell_capacity(t, g.scenario)
        if cap > 0:
            g.submit(t, [Segment(g.marginal_cost(t, g.scenario), cap)])
    res = g.close_round()
    assert res.price == pytest.approx(20)  # hydro is marginal
    for t in g.teams:  # everyone earns (clearing price - own cost) on cleared MW
        assert t.profit == pytest.approx(
            (res.price - g.marginal_cost(t, g.scenario)) * _cleared(res, t.name)
        )


def test_battery_charges_then_discharges_across_rounds():
    g = new_game(7)
    bat = team_with(g, "battery")
    # round 1: charge at a high willingness so it clears
    g.open_round()
    for t in g.teams:
        if t is bat:
            continue
        cap = g.sell_capacity(t, g.scenario)
        if cap > 0:
            g.submit(t, [Segment(g.marginal_cost(t, g.scenario), cap)])
    soc0 = bat.soc  # a small starting charge
    charge_mw = g.charge_capacity(bat)
    g.submit(bat, [Segment(180, charge_mw, side="buy")])
    r1 = g.close_round()
    stored = min(charge_mw, next(a.cleared for a in r1.awards if a.team == bat.name))
    assert bat.soc == pytest.approx(soc0 + stored * TECHS["battery"].efficiency)
    assert bat.profit < 0  # paid to charge

    # round 2: it can now discharge up to its stored energy
    g.open_round()
    assert g.sell_capacity(bat, g.scenario) == pytest.approx(min(600 * bat.share, bat.soc))


def test_cumulative_energy_tracked():
    g = new_game(7)
    g.open_round()
    for t in g.teams:
        cap = g.sell_capacity(t, g.scenario)
        if cap > 0:
            g.submit(t, [Segment(g.marginal_cost(t, g.scenario), cap)])
    res = g.close_round()
    for t in g.teams:
        assert t.energy == pytest.approx(_cleared(res, t.name))


def test_co2_price_flips_coal_and_gas():
    from market.engine.scenario import Scenario

    g = new_game(7)
    coal, gas = team_with(g, "coal"), team_with(g, "gas")
    cheap = Scenario("x", demand=4000, co2_price=0)
    dear = Scenario("x", demand=4000, co2_price=100)
    assert g.marginal_cost(coal, cheap) < g.marginal_cost(gas, cheap)  # coal 30 < gas 50
    assert g.marginal_cost(coal, dear) > g.marginal_cost(gas, dear)  # coal 120 > gas 85


def test_load_shedding_pays_voll():
    from market.engine.tech import VOLL

    g = new_game(7)
    g.open_round()
    for t in g.teams:  # bid only a sliver so demand cannot be met
        if g.sell_capacity(t, g.scenario) > 0:
            g.submit(t, [Segment(g.marginal_cost(t, g.scenario), 1)])
    res = g.close_round()
    assert res.price == VOLL
    assert res.scarce
    coal = team_with(g, "coal")
    assert coal.profit == pytest.approx((VOLL - 30) * _cleared(res, coal.name))


def _cleared(res, team):
    return sum(a.cleared for a in res.awards if a.team == team and a.side == "sell")


# ---- exotic / unconventional bids ------------------------------------------
def test_empty_bid_is_allowed():
    g = new_game(7)
    g.open_round()
    coal = team_with(g, "coal")
    g.submit(coal, [])  # a team may choose to offer nothing
    assert coal.submitted and coal.bid == []


def test_zero_quantity_segment_is_accepted_and_offers_nothing():
    g = new_game(7)
    g.open_round()
    coal = team_with(g, "coal")
    g.submit(coal, [Segment(g.marginal_cost(coal, g.scenario), 0.0)])
    assert coal.submitted


def test_non_finite_bids_are_rejected():
    g = new_game(7)
    g.open_round()
    coal = team_with(g, "coal")
    with pytest.raises(BidError):
        g.submit(coal, [Segment(float("nan"), 100)])
    with pytest.raises(BidError):
        g.submit(coal, [Segment(50, float("inf"))])


def test_storage_hedge_overlapping_prices_rejected():
    g = new_game(7)
    g.open_round()
    bat = team_with(g, "battery")
    with pytest.raises(BidError):  # buy 60 is not below sell 40 -> both could clear
        g.submit(bat, [Segment(40, 20, "sell"), Segment(60, 20, "buy")])


def test_storage_hedge_respects_each_side_capacity():
    g = new_game(7)
    g.open_round()
    bat = team_with(g, "battery")
    with pytest.raises(BidError):  # buy volume exceeds charge capacity
        g.submit(
            bat,
            [
                Segment(80, g.sell_capacity(bat, g.scenario), "sell"),
                Segment(20, g.charge_capacity(bat) + 100, "buy"),
            ],
        )


@pytest.mark.parametrize(
    "supply_price,expect",
    [(10, "charge"), (50, "idle"), (200, "discharge")],
)
def test_storage_hedge_clears_at_most_one_side(supply_price, expect):
    # a battery hedges: sell high (>=80) OR buy low (<=20). Depending on where the
    # rest of the market sets the price, at most one side ever clears.
    from market.engine.scenario import Scenario

    g = Game(scenarios=[Scenario("x", demand=200)])
    g.teams = [Team("bat", "battery", 1.0, 150.0), Team("gen", "coal", 1.0, 0.0)]
    g.open_round()
    g.submit(g.teams[1], [Segment(supply_price, 500)])  # the rest of the market
    g.submit(g.teams[0], [Segment(80, 150, "sell"), Segment(20, 100, "buy")])
    g.close_round()
    bat = g.teams[0]
    if expect == "charge":
        assert bat.last["charged"] > 0 and bat.last["sold"] == 0 and bat.soc > 150
    elif expect == "discharge":
        assert bat.last["sold"] > 0 and bat.last["charged"] == 0 and bat.soc < 150
    else:
        assert bat.last["sold"] == 0 and bat.last["charged"] == 0 and bat.soc == 150


def test_storage_cannot_discharge_more_than_it_has_stored():
    g = new_game(7)
    g.open_round()
    bat = team_with(g, "battery")
    with pytest.raises(BidError):
        g.submit(bat, [Segment(0, bat.soc + 100)])  # more than the small starting charge


def test_identical_bidders_split_dispatch_and_profit_equally():
    from market.engine.scenario import Scenario

    g = Game(scenarios=[Scenario("x", demand=1000)])
    g.teams = [Team("A", "coal", 0.5, 0.0), Team("B", "coal", 0.5, 0.0)]
    g.open_round()
    for t in g.teams:
        g.submit(t, [Segment(50, g.sell_capacity(t, g.scenario))])
    res = g.close_round()
    assert _cleared(res, "A") == pytest.approx(_cleared(res, "B")) == pytest.approx(500)
    assert g.teams[0].profit == pytest.approx(g.teams[1].profit) == pytest.approx((50 - 30) * 500)


def test_average_ask_tracks_bid_weighted_by_cleared():
    from market.engine.scenario import Scenario

    g = Game(scenarios=[Scenario("x", demand=1000)])
    g.teams = [Team("A", "coal", 1.0, 0.0)]
    g.open_round()
    g.submit(g.teams[0], [Segment(45, 2400)])  # bid 45, clears 1000 to meet demand
    g.close_round()
    a = g.teams[0]
    assert a.energy == pytest.approx(1000)
    assert a.ask_value == pytest.approx(45 * 1000)  # -> volume-weighted average ask of 45
