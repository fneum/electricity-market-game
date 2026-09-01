"""Scenario design checks: each scenario must create a real, distinct market effect.

Every scenario is played in a competitive baseline - 7 teams (one per technology,
so the full market capacity is present) all bidding at their true marginal cost.
The clearing price is then set by the residual load, which is exactly what the
scenarios are designed to move.
"""

import random
from dataclasses import replace

import pytest
from market.engine.game import Game, Segment, Team, assign_techs
from market.engine.scenario import CLASSIC, EXTRAS
from market.engine.tech import TECHS


def started(scenarios, n_teams=7, seed=0):
    g = Game(scenarios=list(scenarios))
    g.teams = [Team(f"T{i}", "", 1.0, 0.0) for i in range(n_teams)]
    g.start(random.Random(seed))
    return g


def play(sc, n_teams=7, seed=0):
    g = started([sc], n_teams, seed)
    g.open_round()
    for t in g.teams:
        cap = g.sell_capacity(t, g.scenario)
        if cap > 0:
            g.submit(t, [Segment(g.marginal_cost(t, g.scenario), cap)])
    return g.close_round()


def by_tech(res):
    out = {}
    for a in res.awards:
        if a.side == "sell":
            out[a.key] = out.get(a.key, 0.0) + a.cleared
    return out


def emissions(res):
    return sum(a.cleared * TECHS[a.key].emission_factor for a in res.awards if a.side == "sell")


# The five classic rounds are designed to land on distinct, memorable outcomes.
@pytest.mark.parametrize(
    "idx,price",
    [(0, 20), (1, 20), (2, 30), (3, 20), (4, 0)],
)
def test_classic_round_clears_at_designed_price(idx, price):
    assert play(CLASSIC[idx]).price == pytest.approx(price)


def test_classic_rounds_span_a_range_of_prices():
    prices = [play(sc).price for sc in CLASSIC]
    assert min(prices) == 0  # a fully renewable hour
    assert max(prices) == 30  # an hour that needs coal
    assert len(set(prices)) >= 3  # genuine variety, not one flat outcome


def test_windy_night_runs_on_renewables_alone_at_zero_price():
    res = play(CLASSIC[4])  # 04:00, full wind, no sun, low demand
    assert res.price == 0
    assert emissions(res) == 0
    fossil = {k: v for k, v in by_tech(res).items() if k in ("coal", "gas", "hydro")}
    assert all(v == 0 for v in fossil.values())  # wind alone covers demand
    assert res.volume == pytest.approx(CLASSIC[4].demand)


def test_low_renewable_round_brings_coal_online():
    res = play(CLASSIC[2])  # 17:00, little wind or sun
    assert res.price == 30  # coal is marginal
    assert by_tech(res).get("coal", 0) > 0
    assert emissions(res) > 0  # the only classic round that burns fossil fuel


def test_peak_demand_is_not_the_most_expensive_hour():
    peak = play(CLASSIC[3])  # 20:00, highest demand of the day, but windy
    tight = play(CLASSIC[2])  # 17:00, lower demand, but calm
    assert CLASSIC[3].demand > CLASSIC[2].demand
    assert peak.price < tight.price  # residual load, not demand, sets the price


def test_more_wind_lowers_the_price():
    calm = play(CLASSIC[0])  # 06:00, wind at 20%
    windy = play(CLASSIC[4])  # 04:00, wind at 100%
    assert windy.price < calm.price


def test_carbon_price_raises_price_but_cuts_emissions():
    scen = EXTRAS[1]  # carbon price introduced
    base = play(replace(scen, co2_price=0))
    priced = play(scen)
    assert priced.price > base.price  # carbon cost lifts the clearing price
    assert emissions(priced) < emissions(base)  # ...yet emissions fall
    # the merit order flips: coal is pushed out and gas takes its place
    assert by_tech(base).get("coal", 0) > 0
    assert by_tech(priced).get("coal", 0) == pytest.approx(0)
    assert by_tech(priced).get("gas", 0) > by_tech(base).get("gas", 0)


def test_gas_shock_raises_the_clearing_price():
    scen = EXTRAS[0]  # fuel supply disruption
    base = play(replace(scen, fuel={}))
    shock = play(scen)
    assert shock.price > base.price
    assert shock.price == pytest.approx(120)  # gas is marginal and sets its shocked cost
    assert by_tech(shock).get("gas", 0) > 0


# ---- team-count robustness (played with 6 to 40 teams) ---------------------
TEAM_COUNTS = [6, 7, 8, 13, 27, 40]
ALL_SCENARIOS = CLASSIC + EXTRAS
SCENARIO_IDS = [sc.label for sc in ALL_SCENARIOS]


@pytest.mark.parametrize("sc", ALL_SCENARIOS, ids=SCENARIO_IDS)
@pytest.mark.parametrize("n", TEAM_COUNTS)
def test_clearing_is_invariant_to_team_count(sc, n):
    # the total market capacity is fixed and merely split among teams, so the
    # cleared price and volume must not depend on how many teams are playing.
    ref = play(sc, n_teams=7)
    res = play(sc, n_teams=n)
    assert res.price == pytest.approx(ref.price)
    assert res.volume == pytest.approx(ref.volume)
    # from 7 teams up every technology is present, so emissions match exactly too.
    # at 6 teams the (small) battery drops out, which can shift a little fossil
    # generation but never the price or volume.
    if n >= 7:
        assert emissions(res) == pytest.approx(emissions(ref))


@pytest.mark.parametrize("n", TEAM_COUNTS)
def test_capacity_is_split_not_duplicated(n):
    g = started(CLASSIC, n_teams=n)
    share_sum: dict[str, float] = {}
    for t in g.teams:
        share_sum[t.tech] = share_sum.get(t.tech, 0.0) + t.share
    # every technology present is fully accounted for exactly once across teams
    assert all(s == pytest.approx(1.0) for s in share_sum.values())
    assert all(t.share > 0 for t in g.teams)


@pytest.mark.parametrize(
    "n,distinct",
    [(6, 6), (7, 7), (8, 7), (13, 7), (40, 7)],
)
def test_technology_coverage_scales(n, distinct):
    picks = assign_techs(n, random.Random(0))
    assert len(picks) == n
    assert len(set(picks)) == distinct
    if n >= 7:
        assert set(picks) == set(TECHS)  # every technology represented


def test_only_the_smallest_technology_drops_out_below_full_coverage():
    # with 6 teams (fewer than the 7 technologies) only the battery is left out;
    # it is the smallest player and carries only a marginal charge, so prices are
    # unchanged and the market still makes sense.
    picks = assign_techs(6, random.Random(0))
    assert set(TECHS) - set(picks) == {"battery"}


def test_larger_cohorts_get_smaller_slices():
    def onshore_mw_per_team(n):
        g = started(CLASSIC, n_teams=n)
        team = next(t for t in g.teams if t.tech == "onshore")
        return TECHS["onshore"].capacity * team.share

    assert onshore_mw_per_team(40) < onshore_mw_per_team(7)


def test_total_producer_profit_is_invariant_to_team_count():
    # Neither demand nor per-technology capacity scales with cohort size: the
    # market total is fixed and simply split among teams. So the whole producer
    # "pie" is the same whether 7 or 40 teams play - only each slice is smaller.
    def total_profit(n):
        g = started([CLASSIC[2]], n_teams=n)  # a round where coal is marginal
        g.open_round()
        for t in g.teams:
            cap = g.sell_capacity(t, g.scenario)
            if cap > 0:
                g.submit(t, [Segment(g.marginal_cost(t, g.scenario), cap)])
        g.close_round()
        return sum(t.profit for t in g.teams)

    assert total_profit(40) == pytest.approx(total_profit(7))
