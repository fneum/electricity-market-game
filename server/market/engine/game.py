"""Game state: team assignment, capacity scaling, rounds, profits.

Cross-round storage state (reservoir / battery state of charge) lives here; the
clearing engine stays a pure single-round function. Each round is treated as one
hour, so MW and MWh are interchangeable within a round.
"""

import math
from collections import Counter
from dataclasses import dataclass, field

from .clearing import Bid, Clearing, clear
from .scenario import Scenario
from .tech import PRICE_CAP, PRICE_FLOOR, TECHS, Technology

# Assignment priority. Extra teams are added in this order, so duplicates favour
# conventional generators (non-zero marginal cost, strategically interesting to
# bid) over yet another zero-cost renewable. Battery is last, so it is the single
# role dropped when there are fewer teams than technologies.
DEFAULT_KEYS = ["coal", "gas", "hydro", "onshore", "offshore", "solar", "battery"]


class BidError(ValueError):
    """Invalid bid submitted by a team (reported back to that team only)."""


@dataclass
class Segment:
    price: float
    quantity: float
    side: str = "sell"


@dataclass
class Team:
    name: str
    tech: str
    share: float  # fraction of the technology's market capacity
    soc: float  # MWh stored (storage technologies only)
    profit: float = 0.0
    energy: float = 0.0  # cumulative MWh sold over the game
    ask_value: float = 0.0  # cumulative sum of (bid price * MWh sold), for the average ask
    bid: list[Segment] = field(default_factory=list)
    submitted: bool = False
    last: dict = field(default_factory=dict)  # breakdown of the most recent round

    @property
    def t(self) -> Technology:
        return TECHS[self.tech]


def assign_techs(n: int, rng, keys: list[str] = DEFAULT_KEYS) -> list[str]:
    """Pick a technology for each of ``n`` teams (cycling ``keys`` so the first
    slots cover every technology and further teams follow the priority order),
    then shuffle who gets what."""
    picks = [keys[i % len(keys)] for i in range(n)]
    rng.shuffle(picks)
    return picks


@dataclass
class Game:
    scenarios: list[Scenario]
    teams: list[Team] = field(default_factory=list)
    phase: str = "LOBBY"  # LOBBY | BIDDING | CLEARED | FINISHED
    round_no: int = 0  # 1-based index of the current/last round
    clearing: Clearing | None = None
    capacities: dict[str, float] = field(default_factory=dict)  # per-game MW overrides

    def capacity(self, key: str) -> float:
        return self.capacities.get(key, TECHS[key].capacity)

    @property
    def scenario(self) -> Scenario | None:
        if 1 <= self.round_no <= len(self.scenarios):
            return self.scenarios[self.round_no - 1]
        return None

    @property
    def n_rounds(self) -> int:
        return len(self.scenarios)

    # ---- lobby ----------------------------------------------------------
    def start(self, rng) -> None:
        if len(self.teams) < 2:
            raise BidError("Need at least two teams to start.")
        picks = assign_techs(len(self.teams), rng)
        counts = Counter(picks)
        for team, key in zip(self.teams, picks, strict=True):
            t = TECHS[key]
            team.tech = key
            team.share = 1 / counts[key]
            team.soc = t.initial_soc * team.share
        self.round_no = 0
        self.phase = "LOBBY"

    # ---- capacity limits ------------------------------------------------
    def sell_capacity(self, team: Team, sc: Scenario) -> float:
        t = team.t
        cap = self.capacity(t.key) * team.share
        if t.variable:
            cap *= sc.availability.get(t.key, 0.0)
        cap = max(0.0, cap - sc.outages.get(t.key, 0.0) * team.share)
        if t.is_storage:
            cap = min(cap, team.soc)
        return cap

    def charge_capacity(self, team: Team) -> float:
        t = team.t
        if not t.is_storage:
            return 0.0
        room = (t.energy * team.share - team.soc) / t.efficiency
        return max(0.0, min(t.charge_power * team.share, room))

    def marginal_cost(self, team: Team, sc: Scenario) -> float:
        return team.t.marginal_cost(sc.co2_price, sc.fuel.get(team.tech))

    # ---- rounds ---------------------------------------------------------
    def open_round(self) -> None:
        if self.phase not in ("LOBBY", "CLEARED"):
            raise BidError("Finish the current round first.")
        if self.round_no >= self.n_rounds:
            raise BidError("No more rounds configured.")
        self.round_no += 1
        self.phase = "BIDDING"
        self.clearing = None
        for team in self.teams:
            team.bid = []
            team.submitted = False

    def submit(self, team: Team, segments: list[Segment]) -> None:
        if self.phase != "BIDDING":
            raise BidError("Bidding is closed.")
        sc = self.scenario
        assert sc is not None
        self._validate(team, segments, sc)
        team.bid = segments
        team.submitted = True

    def _validate(self, team: Team, segments: list[Segment], sc: Scenario) -> None:
        sides = {s.side for s in segments}
        if sides - {"sell", "buy"}:
            raise BidError("Each segment must be a sell or a buy.")
        if "buy" in sides and not team.t.is_storage:
            raise BidError("Only storage technologies can buy (charge).")
        for s in segments:
            if not (math.isfinite(s.price) and math.isfinite(s.quantity)):
                raise BidError("Prices and quantities must be finite numbers.")
            if s.quantity < 0:
                raise BidError("Quantities cannot be negative.")
            if not PRICE_FLOOR <= s.price <= PRICE_CAP:
                raise BidError(f"Prices must be between {PRICE_FLOOR:.0f} and {PRICE_CAP:.0f}.")
        sells = [s for s in segments if s.side == "sell"]
        buys = [s for s in segments if s.side == "buy"]
        # storage may hedge (sell high OR buy low), but the prices must not overlap,
        # so at most one side ever clears - never charging and discharging at once.
        if sells and buys and max(b.price for b in buys) >= min(s.price for s in sells):
            raise BidError("Every buy price must be below every sell price.")
        self._check_limit(sum(s.quantity for s in sells), self.sell_capacity(team, sc), "sell")
        self._check_limit(sum(b.quantity for b in buys), self.charge_capacity(team), "charge")

    @staticmethod
    def _check_limit(total: float, limit: float, what: str) -> None:
        if total > limit + 1e-6:
            raise BidError(
                f"You can {what} at most {limit:.0f} MW this round (you bid {total:.0f})."
            )

    def close_round(self) -> Clearing:
        if self.phase != "BIDDING":
            raise BidError("No open round to clear.")
        sc = self.scenario
        assert sc is not None
        bids = self._collect_bids(sc)
        res = clear(bids, sc.demand)
        self._settle(res)
        self.clearing = res
        self.phase = "CLEARED"
        if self.round_no >= self.n_rounds:
            self.phase = "FINISHED"
        return res

    def _collect_bids(self, sc: Scenario) -> list[Bid]:
        bids = []
        for team in self.teams:
            cost = self.marginal_cost(team, sc)
            for s in team.bid:
                c = cost if s.side == "sell" else 0.0
                bids.append(Bid(team.name, team.tech, s.price, s.quantity, c, s.side))
        return bids

    def _settle(self, res: Clearing) -> None:
        zero = {"sold": 0.0, "charged": 0.0, "revenue": 0.0, "cost": 0.0, "ask": 0.0}
        agg = {t.name: zero.copy() for t in self.teams}
        for a in res.awards:
            d = agg[a.team]
            if a.side == "sell":
                d["sold"] += a.cleared
                d["revenue"] += res.price * a.cleared
                d["cost"] += a.cost * a.cleared
                d["ask"] += a.price * a.cleared
            else:
                d["charged"] += a.cleared
        for team in self.teams:
            d = agg[team.name]
            paid = res.price * d["charged"]
            delta = d["revenue"] - d["cost"] - paid
            team.profit += delta
            team.energy += d["sold"]
            team.ask_value += d["ask"]
            if team.t.is_storage:
                team.soc = max(0.0, team.soc - d["sold"]) + d["charged"] * team.t.efficiency
            team.last = {"price": res.price, "paid": paid, "delta": delta, **d}

    def leaderboard(self) -> list[Team]:
        return sorted(self.teams, key=lambda t: -t.profit)
