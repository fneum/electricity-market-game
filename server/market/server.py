"""Network layer: games, WebSockets, static files. No market logic lives here.

Each game keeps a lecturer (who created it) and any number of student teams,
all in RAM. Every action triggers one personalized broadcast: teams see their
own role, bid and result; the lecturer sees everything (the projector view).
"""

import math
import random
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine.game import BidError, Game, Segment, Team
from .engine.scenario import PRESETS, Scenario
from .engine.tech import PRICE_CAP, PRICE_FLOOR, TECHS, VOLL

ADJ = ("bright", "windy", "sunny", "peak", "green", "clean", "swift", "sparky", "charged", "steady")
NOUN = ("grid", "watt", "joule", "volt", "amp", "turbine", "panel", "spark", "current", "power")

app = FastAPI(title="Electricity Market Game")
GAMES: dict[str, "Room"] = {}
TTL = 24 * 3600


@dataclass
class Session:
    token: str
    role: str  # "lecturer" | "team"
    name: str
    ws: WebSocket | None = None


@dataclass
class Room:
    id: str
    game: Game
    admin_token: str
    sessions: list[Session] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)
    reveal: bool = True  # show each team's technology to students on the leaderboard
    final: bool = False  # lecturer has revealed the final results page
    last_active: float = field(default_factory=time.time)

    async def broadcast(self) -> None:
        for s in self.sessions:
            if s.ws:
                try:
                    await s.ws.send_json(view(self, s))
                except Exception:
                    s.ws = None


def new_id() -> str:
    while True:
        gid = f"{random.choice(ADJ)}-{random.choice(NOUN)}-{random.randint(10, 99)}"
        if gid not in GAMES:
            return gid


def gc() -> None:
    cutoff = time.time() - TTL
    for gid in [g for g, r in GAMES.items() if r.last_active < cutoff]:
        del GAMES[gid]


def _scenario_to_form(sc: Scenario) -> dict:
    """A Scenario as the editable fields shown in the create-game panel."""
    return {
        "label": sc.label,
        "demand": sc.demand,
        "wind": round(sc.availability.get("onshore", 0.0) * 100),
        "sun": round(sc.availability.get("solar", 0.0) * 100),
        "co2_price": sc.co2_price,
        "gas_cost": sc.fuel.get("gas", TECHS["gas"].base_cost),  # show the normal cost, not blank
        "coal_outage": sc.outages.get("coal", 0.0),
        "note": sc.note,
    }


def _form_to_scenario(f: dict) -> Scenario:
    def num(key, default=0.0):
        v = f.get(key, default)
        return default if v in (None, "") else float(v)

    wind = num("wind") / 100
    gas = num("gas_cost", None) if f.get("gas_cost") not in (None, "") else None
    outage = num("coal_outage")
    return Scenario(
        label=str(f.get("label", "")).strip()[:40] or "Round",
        demand=num("demand"),
        availability={"onshore": wind, "offshore": wind, "solar": num("sun") / 100},
        co2_price=num("co2_price"),
        fuel={"gas": gas} if gas is not None else {},
        outages={"coal": outage} if outage > 0 else {},
        note=str(f.get("note", "")).strip()[:200],
    )


@app.get("/api/presets")
def presets() -> dict:
    """Preset scenario sets as editable forms, for pre-filling the create panel."""
    return {name: [_scenario_to_form(s) for s in scs] for name, scs in PRESETS.items()}


@app.get("/api/technologies")
def technologies() -> list[dict]:
    """Technologies with their default installed capacity, for the create panel."""
    return [
        {"key": k, "name": t.name, "color": t.color, "capacity": t.capacity}
        for k, t in TECHS.items()
    ]


def _capacities(raw: dict) -> dict[str, float]:
    out = {}
    for k, v in raw.items():
        if k not in TECHS:
            raise HTTPException(400, f"Unknown technology: {k}")
        try:
            val = float(v)
        except (TypeError, ValueError) as e:
            raise HTTPException(400, "Capacities must be numbers.") from e
        if not math.isfinite(val) or val <= 0:
            raise HTTPException(400, "Capacities must be positive.")
        out[k] = val
    return out


@app.post("/api/game")
def create_game(cfg: dict | None = None) -> dict:
    gc()
    cfg = cfg or {}
    forms = cfg.get("scenarios")
    if forms is not None:  # custom scenarios edited in the panel
        if not forms:
            raise HTTPException(400, "A game needs at least one round.")
        try:
            scenarios = [_form_to_scenario(f) for f in forms]
        except (TypeError, ValueError) as e:
            raise HTTPException(400, f"Invalid scenario: {e}") from e
        if any(sc.demand <= 0 for sc in scenarios):
            raise HTTPException(400, "Every round needs a demand above 0.")
    else:  # fall back to a named preset
        preset = cfg.get("preset", "classic")
        scenarios = list(PRESETS.get(preset, PRESETS["classic"]))
        rounds = cfg.get("rounds")
        if rounds:
            scenarios = scenarios[: int(rounds)]
    capacities = _capacities(cfg.get("capacities") or {})
    gid = new_id()
    game = Game(scenarios=scenarios, capacities=capacities)
    room = Room(id=gid, game=game, admin_token=secrets.token_hex(16))
    GAMES[gid] = room
    return {"id": gid, "admin_token": room.admin_token}


# ---------- view (personalized state) ------------------------------------
def _sc_view(room: Room) -> dict | None:
    sc = room.game.scenario
    if sc is None:
        return None
    return {
        "label": sc.label,
        "demand": sc.demand,
        "availability": sc.availability,
        "co2_price": sc.co2_price,
        "fuel": sc.fuel,
        "outages": sc.outages,
        "note": sc.note,
    }


def _tech_view(key: str) -> dict:
    t = TECHS[key]
    return {"key": key, "name": t.name, "color": t.color, "storage": t.is_storage}


def _emissions(res) -> float:
    return sum(a.cleared * TECHS[a.key].emission_factor for a in res.awards if a.side == "sell")


def _bid_view(a, reveal: bool, viewer: str | None) -> dict:
    team = a.team if reveal else ("You" if a.team == viewer else "Another team")
    return {
        "team": team,
        "key": a.key,
        "tech": TECHS[a.key].name,
        "color": TECHS[a.key].color,
        "price": a.price,
        "quantity": a.quantity,
        "cleared": a.cleared,
        "cost": a.cost,
    }


def _clearing_view(res, reveal: bool, viewer: str | None) -> dict:
    sells = sorted((a for a in res.awards if a.side == "sell"), key=lambda a: a.price)
    buys = sorted((a for a in res.awards if a.side == "buy"), key=lambda a: -a.price)
    return {
        "price": res.price,
        "volume": res.volume,
        "demand": res.demand,
        "served": res.served,
        "unserved": res.unserved,
        "scarce": res.scarce,
        "voll": VOLL,
        "emissions": _emissions(res),
        "supply": [_bid_view(a, reveal, viewer) for a in sells],
        "demand_bids": [_bid_view(a, reveal, viewer) for a in buys],
    }


def _role_card(room: Room, team: Team) -> dict:
    g, sc, t = room.game, room.game.scenario, team.t
    card = {
        **_tech_view(team.tech),
        "blurb": t.blurb,
        "share": team.share,
        "capacity_total": g.capacity(t.key) * team.share,
        "base_cost": t.base_cost,
        "emission_factor": t.emission_factor,
        "variable": t.variable,
        "floor": PRICE_FLOOR,
        "cap": PRICE_CAP,
    }
    if sc is not None:
        card["cost"] = g.marginal_cost(team, sc)
        card["sell_capacity"] = g.sell_capacity(team, sc)
        card["charge_capacity"] = g.charge_capacity(team)
        if t.variable:
            card["availability"] = sc.availability.get(team.tech, 0.0)
    if t.is_storage:
        card["soc"] = team.soc
        card["energy"] = t.energy * team.share
        card["charge_power"] = t.charge_power * team.share
        card["efficiency"] = t.efficiency
    return card


def _role_of(team: Team, reveal: bool) -> dict:
    if reveal and team.tech:
        t = team.t
        return {"tech": t.name, "color": t.color}
    return {"tech": None, "color": None}


def _standing(t: Team, reveal: bool) -> dict:
    sold = t.energy
    return {
        "name": t.name,
        "profit": t.profit,
        "energy": sold,
        "cost": TECHS[t.tech].base_cost if (reveal and t.tech) else None,  # base fuel/O&M cost
        "vwab": (t.ask_value / sold) if sold > 1e-9 else None,  # volume-weighted average ask
        "profit_per_mwh": (t.profit / sold) if sold > 1e-9 else None,
        **_role_of(t, reveal),
    }


def view(room: Room, s: Session) -> dict:
    g = room.game
    # the lecturer always sees roles; students see them when the reveal toggle is on
    reveal = s.role == "lecturer" or room.reveal
    base = {
        "type": "state",
        "game": room.id,
        "role": s.role,
        "phase": g.phase,
        "round_no": g.round_no,
        "n_rounds": g.n_rounds,
        "reveal": room.reveal,
        "final": room.final,
        "scenario": _sc_view(room),
        "teams": [
            {"name": t.name, "profit": t.profit, "submitted": t.submitted, **_role_of(t, reveal)}
            for t in g.teams
        ],
        "leaderboard": [_standing(t, reveal) for t in g.leaderboard()],
    }
    if g.clearing is not None:
        base["clearing"] = _clearing_view(g.clearing, reveal, s.name if s.role == "team" else None)
    if s.role == "team":
        team = next((t for t in g.teams if t.name == s.name), None)
        if team is not None:
            base["you"] = {
                "name": team.name,
                "role_card": _role_card(room, team) if team.tech else None,
                "bid": [
                    {"price": x.price, "quantity": x.quantity, "side": x.side} for x in team.bid
                ],
                "submitted": team.submitted,
                "profit": team.profit,
                "last": team.last,
            }
    return base


# ---------- actions ------------------------------------------------------
def join(room: Room, ws: WebSocket, msg: dict) -> Session:
    role = msg.get("role", "team")
    token = msg.get("token") or secrets.token_hex(16)
    for s in room.sessions:  # reconnect by token
        if s.token == token:
            s.ws = ws
            return s
    if role == "lecturer":
        if msg.get("token") != room.admin_token:
            raise BidError("Wrong lecturer link.")
        s = Session(token=room.admin_token, role="lecturer", name="Lecturer", ws=ws)
        room.sessions.append(s)
        return s
    name = (msg.get("name") or "").strip()[:24]
    if not name:
        raise BidError("Please enter a team name.")
    for s in room.sessions:  # reconnect by name (browser crashed)
        if s.role == "team" and s.name == name and s.ws is None:
            s.ws, s.token = ws, token
            return s
    if any(s.role == "team" and s.name == name for s in room.sessions):
        raise BidError("That team name is taken.")
    if room.game.phase != "LOBBY":
        raise BidError("The game has already started.")
    room.game.teams.append(Team(name=name, tech="", share=1.0, soc=0.0))
    s = Session(token=token, role="team", name=name, ws=ws)
    room.sessions.append(s)
    return s


def act(room: Room, s: Session, msg: dict) -> None:
    a = msg.get("action")
    g = room.game
    if a in ("start", "open_round", "close_round", "reset", "reveal", "show_final"):
        if s.role != "lecturer":
            raise BidError("Only the lecturer controls the game.")
        if a == "reveal":
            room.reveal = bool(msg["value"]) if "value" in msg else not room.reveal
        elif a == "show_final":
            room.final = bool(msg["value"]) if "value" in msg else not room.final
        elif a == "start":
            g.start(room.rng)
        elif a == "open_round":
            g.open_round()
        elif a == "close_round":
            g.close_round()
        elif a == "reset":
            g.phase, g.round_no, g.clearing = "LOBBY", 0, None
            room.final = False
            for t in g.teams:
                t.profit, t.energy, t.ask_value, t.soc = 0.0, 0.0, 0.0, 0.0
                t.bid, t.submitted, t.last = [], False, {}
    elif a == "bid":
        if s.role != "team":
            raise BidError("Only teams submit bids.")
        team = next(t for t in g.teams if t.name == s.name)
        g.submit(team, _parse_segments(msg.get("segments", [])))
    else:
        raise BidError(f"Unknown action: {a}")


def _parse_segments(raw) -> list[Segment]:
    if not isinstance(raw, list):
        raise BidError("Your bid was malformed.")
    out = []
    for x in raw:
        try:
            out.append(Segment(float(x["price"]), float(x["quantity"]), str(x.get("side", "sell"))))
        except (KeyError, TypeError, ValueError) as e:
            raise BidError("Each bid row needs a numeric price and quantity.") from e
    return out


@app.websocket("/ws/{game_id}")
async def ws_endpoint(ws: WebSocket, game_id: str) -> None:
    await ws.accept()
    gc()
    room = GAMES.get(game_id)
    if room is None:
        await ws.send_json({"type": "error", "text": "This game does not exist."})
        await ws.close()
        return
    session: Session | None = None
    try:
        while True:
            try:
                msg = await ws.receive_json()
            except ValueError:
                continue  # ignore non-JSON frames rather than dropping the client
            if not isinstance(msg, dict):
                continue  # only object messages carry an action
            room.last_active = time.time()
            try:
                if msg.get("action") == "join":
                    session = join(room, ws, msg)
                    await ws.send_json(
                        {"type": "welcome", "token": session.token, "role": session.role}
                    )
                elif session is None:
                    raise BidError("Please join first.")
                else:
                    act(room, session, msg)
            except (BidError, ValueError) as e:
                await ws.send_json({"type": "error", "text": str(e)})
                continue
            await room.broadcast()
    except WebSocketDisconnect:
        if session and session.ws is ws:
            session.ws = None
            await room.broadcast()


# ---------- static frontend ----------------------------------------------
DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    @app.get("/g/{game_id}")
    def index(game_id: str = "") -> FileResponse:
        return FileResponse(DIST / "index.html")
