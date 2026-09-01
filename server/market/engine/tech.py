"""Technology catalogue for the market.

Capacities are market totals in MW (twice the per-player figures in the paper
role sheets, where two players shared each technology). Costs are in EUR/MWh
excluding CO2; the effective marginal cost adds ``co2_price * emission_factor``.

Storage technologies (hydro reservoir, battery) carry an energy budget that is
tracked across rounds by the game layer; ``charge_power`` lets them buy
electricity (pumping / charging) and ``efficiency`` is the round-trip efficiency.
"""

from dataclasses import dataclass

VOLL = 3000.0  # EUR/MWh, value of lost load: price paid when demand is shed
PRICE_CAP = VOLL  # no bid may exceed the value of lost load (above it, shedding is cheaper)
PRICE_FLOOR = -500.0  # negative bids are allowed (e.g. to avoid being switched off)


@dataclass(frozen=True)
class Technology:
    key: str
    name: str
    capacity: float  # MW, market total (generation / discharge power)
    base_cost: float  # EUR/MWh, excluding CO2
    emission_factor: float = 0.0  # tCO2/MWh
    color: str = "#888888"
    variable: bool = False  # weather-dependent (availability applies)
    energy: float = 0.0  # MWh storage budget (0 => not storage)
    initial_soc: float = 0.0  # MWh stored at game start
    charge_power: float = 0.0  # MW max charging (pumping / battery in)
    # round-trip efficiency: the whole loss is applied once, when charging
    # (discharging is lossless), so energy_out / energy_in == efficiency.
    efficiency: float = 1.0
    blurb: str = ""

    @property
    def is_storage(self) -> bool:
        return self.energy > 0

    def marginal_cost(self, co2_price: float = 0.0, base_cost: float | None = None) -> float:
        base = self.base_cost if base_cost is None else base_cost
        return base + co2_price * self.emission_factor


TECHS: dict[str, Technology] = {
    t.key: t
    for t in [
        Technology(
            key="coal",
            name="Coal",
            capacity=2400,
            base_cost=30,
            emission_factor=0.90,
            color="#2f3e46",
            blurb=(
                "A coal-fired power station burns coal to boil water into steam, which spins "
                "a turbine to make electricity. It can run at any time of day. Burning coal "
                "costs money for every unit of electricity produced, and it releases a large "
                "amount of carbon dioxide."
            ),
        ),
        Technology(
            key="gas",
            name="Gas",
            capacity=2200,
            base_cost=50,
            emission_factor=0.35,
            color="#ff7b00",
            blurb=(
                "A gas-fired power station burns natural gas to make electricity and can be "
                "switched on whenever it is needed. The fuel costs money for every unit "
                "produced, and it releases carbon dioxide, though less than coal does."
            ),
        ),
        Technology(
            key="hydro",
            name="Reservoir Hydro",
            capacity=2000,
            base_cost=20,
            emission_factor=0.0,
            color="#00b4d8",
            energy=6000,
            initial_soc=4000,  # not full, so pumped storage has room to charge from round 1
            charge_power=600,
            efficiency=0.80,
            blurb=(
                "A hydropower station lets water fall from a reservoir through a turbine to "
                "make electricity. Running it costs very little. The reservoir holds only a "
                "limited amount of water for the whole game, so energy you sell now cannot be "
                "sold again later. Your station can also pump water back up, buying "
                "electricity now to store it and sell in a later round."
            ),
        ),
        Technology(
            key="onshore",
            name="Onshore Wind",
            capacity=3800,
            base_cost=0,
            emission_factor=0.0,
            color="#06d6a0",
            variable=True,
            blurb=(
                "An onshore wind farm makes electricity from the wind blowing over land. Once "
                "it is built it costs almost nothing to run and releases no carbon dioxide, "
                "but it can only produce as much as the wind allows at that moment."
            ),
        ),
        Technology(
            key="offshore",
            name="Offshore Wind",
            capacity=1200,
            base_cost=0,
            emission_factor=0.0,
            color="#3a0ca3",
            variable=True,
            blurb=(
                "An offshore wind farm stands out at sea, where the wind is stronger and "
                "steadier than on land. It costs almost nothing to run and releases no carbon "
                "dioxide, but how much it produces still depends on the wind."
            ),
        ),
        Technology(
            key="solar",
            name="Solar PV",
            capacity=800,
            base_cost=0,
            emission_factor=0.0,
            color="#ffd60a",
            variable=True,
            blurb=(
                "A solar farm turns sunlight straight into electricity using panels. It costs "
                "almost nothing to run and releases no carbon dioxide, but it only produces "
                "while the sun is shining, and nothing at night."
            ),
        ),
        Technology(
            key="battery",
            name="Battery",
            capacity=600,
            base_cost=0,
            emission_factor=0.0,
            color="#f72585",
            energy=1200,
            initial_soc=150,  # a small starting charge, so it can already sell in round 1
            charge_power=600,
            efficiency=0.90,
            blurb=(
                "A battery stores electricity and gives it back later. It starts with only a "
                "small charge. You can buy electricity to charge it and sell that energy again "
                "in a later round, but some of it is always lost along the way. It makes no "
                "electricity of its own and releases no carbon dioxide."
            ),
        ),
    ]
}
