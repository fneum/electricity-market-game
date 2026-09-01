"""Round scenarios: demand, weather (renewable availability), CO2 and fuel shocks.

The classic preset reproduces the five well-tested instances from the paper
role-play. Extra scenarios add a CO2 price and a gas-price shock so the lecturer
can show the merit order reorder. Demand is in MWh; availability is the
deliverable share (0..1) of a variable technology's capacity.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    label: str
    demand: float  # MWh
    availability: dict[str, float] = field(default_factory=dict)  # tech -> 0..1
    co2_price: float = 0.0  # EUR/tCO2
    fuel: dict[str, float] = field(default_factory=dict)  # tech -> base_cost override
    outages: dict[str, float] = field(default_factory=dict)  # tech -> MW removed
    note: str = ""

    def wind(self, key: str) -> float:
        return self.availability.get(key, 0.0)


def _weather(wind: float, solar: float) -> dict[str, float]:
    return {"onshore": wind, "offshore": wind, "solar": solar}


CLASSIC: list[Scenario] = [
    Scenario(
        "06:00",
        demand=3000,
        availability=_weather(0.20, 0.10),
        note="It is early in the morning. Wind speeds are low and the sun has barely risen.",
    ),
    Scenario(
        "11:00",
        demand=4000,
        availability=_weather(0.50, 0.90),
        note="It is late morning. The sky is clear and a steady breeze is blowing.",
    ),
    Scenario(
        "17:00",
        demand=4500,
        availability=_weather(0.10, 0.20),
        outages={"coal": 500},
        note="It is early evening. The wind has dropped and the sun is low. "
        "One large power station has unexpectedly gone offline.",
    ),
    Scenario(
        "20:00",
        demand=5500,
        availability=_weather(0.80, 0.20),
        note="It is evening, and electricity use has reached its highest point of the day. "
        "The wind is strong while the sun is setting.",
    ),
    Scenario(
        "04:00",
        demand=2000,
        availability=_weather(1.00, 0.00),
        note="It is the middle of the night. Very little electricity is being used and the "
        "wind is blowing hard.",
    ),
]

EXTRAS: list[Scenario] = [
    Scenario(
        "Fuel supply disruption",
        demand=5200,
        availability=_weather(0.10, 0.10),
        fuel={"gas": 120},
        note="Demand is high, wind and sun are scarce, and a disruption to fuel supplies has "
        "sharply raised the running cost of some power stations this round.",
    ),
    Scenario(
        "Carbon price introduced",
        demand=4500,
        availability=_weather(0.20, 0.20),
        co2_price=100,
        note="From now on a charge applies for every tonne of carbon dioxide a power station "
        "releases.",
    ),
]

PRESETS: dict[str, list[Scenario]] = {
    "classic": CLASSIC,
    "extended": CLASSIC + EXTRAS,
}
