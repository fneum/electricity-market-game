"""Two-sided uniform-price market clearing (the merit order).

Sell bids (generation, storage discharge) form an upward supply curve; buy bids
(pumping, battery charging) plus the inelastic system demand form a downward
demand curve. They cross at the clearing price. Everyone who cleared is paid (or
pays) that single price, regardless of what they bid.

Edge cases handled:
- marginal bid partially dispatched (a bid sitting between two price levels),
- several bids tied at the marginal price -> split pro rata,
- demand landing exactly on a price-level boundary,
- demand exceeding supply -> the missing load is shed at the value of lost load
  (VOLL) and everyone who runs is paid VOLL (no charging happens then).
"""

from dataclasses import dataclass

from .tech import VOLL

EPS = 1e-9


@dataclass
class Bid:
    team: str
    key: str  # technology key
    price: float  # EUR/MWh
    quantity: float  # MW
    cost: float = 0.0  # marginal cost, for profit (sell side only)
    side: str = "sell"  # "sell" or "buy"


@dataclass
class Award:
    team: str
    key: str
    side: str
    price: float  # the bid price
    quantity: float  # the bid quantity
    cleared: float  # MW actually cleared
    cost: float


@dataclass
class Clearing:
    price: float
    volume: float  # total generation dispatched (base demand + charging)
    demand: float  # inelastic system demand
    served: float  # base demand actually served
    unserved: float
    awards: list[Award]

    @property
    def scarce(self) -> bool:
        return self.unserved > EPS


def _supply(sells: list[Bid], p: float) -> float:
    return sum(b.quantity for b in sells if b.price <= p + EPS)


def _demand(buys: list[Bid], base: float, p: float) -> float:
    return base + sum(b.quantity for b in buys if b.price >= p - EPS)


def clear(bids: list[Bid], demand: float, voll: float = VOLL) -> Clearing:
    sells = [b for b in bids if b.side == "sell"]
    buys = [b for b in bids if b.side == "buy"]

    prices = sorted({b.price for b in sells} | {b.price for b in buys})
    price = voll
    found = False
    for p in prices:
        if _supply(sells, p) + EPS >= _demand(buys, demand, p):
            price, found = p, True
            break

    if not found:  # scarcity: supply cannot meet demand -> shed load at VOLL
        matched = _supply(sells, voll)  # every offer runs, no charging
        served = min(demand, matched)
        awards = [_award(b, b.quantity) for b in sells]
        awards += [_award(b, 0.0) for b in buys]
        return Clearing(voll, matched, demand, served, demand - served, awards)

    matched = _demand(buys, demand, price)
    sell_awards = _dispatch(sells, matched, price)
    buy_awards = [_award(b, b.quantity if b.price >= price - EPS else 0.0) for b in buys]
    return Clearing(price, matched, demand, demand, 0.0, sell_awards + buy_awards)


def _dispatch(sells: list[Bid], target: float, price: float) -> list[Award]:
    """Dispatch cheapest first; split the marginal price level pro rata."""
    cheaper = [b for b in sells if b.price < price - EPS]
    marginal = [b for b in sells if abs(b.price - price) <= EPS]
    filled = sum(b.quantity for b in cheaper)
    remaining = max(0.0, target - filled)
    marginal_qty = sum(b.quantity for b in marginal)
    ratio = remaining / marginal_qty if marginal_qty > EPS else 0.0
    awards = [_award(b, b.quantity) for b in cheaper]
    awards += [_award(b, b.quantity * ratio) for b in marginal]
    awards += [_award(b, 0.0) for b in sells if b.price > price + EPS]
    return awards


def _award(b: Bid, cleared: float) -> Award:
    return Award(b.team, b.key, b.side, b.price, b.quantity, cleared, b.cost)
