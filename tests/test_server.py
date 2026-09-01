"""Smoke test: a lecturer and student teams play a round over WebSockets."""

from fastapi.testclient import TestClient
from market.server import app


def test_full_round_over_websockets():
    client = TestClient(app)
    created = client.post("/api/game", json={"preset": "classic", "rounds": 2}).json()
    gid, admin = created["id"], created["admin_token"]

    lec = client.websocket_connect(f"/ws/{gid}").__enter__()
    lec.send_json({"action": "join", "role": "lecturer", "token": admin})
    assert lec.receive_json()["type"] == "welcome"
    lec.receive_json()  # state broadcast

    teams = []
    for i in range(6):
        ws = client.websocket_connect(f"/ws/{gid}").__enter__()
        ws.send_json({"action": "join", "role": "team", "name": f"Team{i}"})
        assert ws.receive_json()["type"] == "welcome"
        teams.append(ws)
        _drain([lec, *teams])

    lec.send_json({"action": "start"})
    states = _drain([lec, *teams])
    assert states[0]["phase"] == "LOBBY"
    assert all(t["tech"] for t in states[0]["teams"])  # everyone got a technology

    lec.send_json({"action": "open_round"})
    states = _drain([lec, *teams])
    assert states[0]["phase"] == "BIDDING"

    for i, ws in enumerate(teams):
        you = states[i + 1]["you"]
        cap = you["role_card"]["sell_capacity"]
        cost = you["role_card"]["cost"]
        if cap > 0:
            ws.send_json({"action": "bid", "segments": [{"price": cost, "quantity": cap}]})
            _drain([lec, *teams])

    lec.send_json({"action": "close_round"})
    states = _drain([lec, *teams])
    assert states[0]["phase"] == "CLEARED"
    clearing = states[0]["clearing"]
    assert clearing["volume"] > 0
    assert clearing["price"] >= 0
    assert clearing["demand"] == 3000

    # a team's own result is reported back to it
    assert "last" in states[1]["you"]

    # non-lecturer cannot drive the game
    teams[0].send_json({"action": "start"})
    assert teams[0].receive_json()["type"] == "error"

    for ws in [lec, *teams]:
        ws.__exit__(None, None, None)


def test_bad_lecturer_token_rejected():
    client = TestClient(app)
    gid = client.post("/api/game").json()["id"]
    ws = client.websocket_connect(f"/ws/{gid}").__enter__()
    ws.send_json({"action": "join", "role": "lecturer", "token": "nope"})
    assert ws.receive_json()["type"] == "error"
    ws.__exit__(None, None, None)


def test_duplicate_team_name_guardrail():
    import pytest
    from market.engine.game import BidError, Game
    from market.engine.scenario import PRESETS
    from market.server import Room, join

    class FakeWS:
        pass

    room = Room(id="x", game=Game(scenarios=list(PRESETS["classic"])), admin_token="a")
    join(room, FakeWS(), {"role": "team", "name": "Alpha"})
    with pytest.raises(BidError):  # taken while the first team is still connected
        join(room, FakeWS(), {"role": "team", "name": "Alpha"})
    room.sessions[0].ws = None  # the first team drops off
    s = join(room, FakeWS(), {"role": "team", "name": "Alpha"})  # name can be reclaimed
    assert s.name == "Alpha" and s.ws is not None
    assert len(room.game.teams) == 1  # no duplicate team was created


def _drain(wss):
    out = []
    for ws in wss:
        msg = ws.receive_json()
        assert msg["type"] == "state"
        out.append(msg)
    return out


def test_presets_endpoint_returns_editable_forms():
    client = TestClient(app)
    p = client.get("/api/presets").json()
    assert set(p) == {"classic", "extended"}
    assert len(p["classic"]) == 5
    row = p["classic"][0]
    fields = {"label", "demand", "wind", "sun", "co2_price", "gas_cost", "coal_outage", "note"}
    assert set(row) >= fields


def test_create_game_with_custom_scenarios():
    from market.server import GAMES

    client = TestClient(app)
    r = client.post(
        "/api/game",
        json={
            "scenarios": [
                {"label": "Custom", "demand": 1234, "wind": 50, "sun": 10,
                 "co2_price": 25, "gas_cost": 90, "coal_outage": 300, "note": "hi"}
            ]
        },
    ).json()
    sc = GAMES[r["id"]].game.scenarios[0]
    assert sc.label == "Custom" and sc.demand == 1234
    assert sc.availability == {"onshore": 0.5, "offshore": 0.5, "solar": 0.1}
    assert sc.co2_price == 25 and sc.fuel == {"gas": 90.0} and sc.outages == {"coal": 300.0}


def test_create_game_rejects_invalid_scenario():
    client = TestClient(app)
    assert client.post("/api/game", json={"scenarios": [{"demand": 0}]}).status_code == 400
    assert client.post("/api/game", json={"scenarios": []}).status_code == 400


def test_parse_segments_rejects_malformed_input():
    import pytest
    from market.engine.game import BidError
    from market.server import _parse_segments

    with pytest.raises(BidError):
        _parse_segments([{"price": 50}])  # missing quantity
    with pytest.raises(BidError):
        _parse_segments([{"price": "x", "quantity": 1}])  # non-numeric
    with pytest.raises(BidError):
        _parse_segments("not a list")
    ok = _parse_segments([{"price": 50, "quantity": 100}])
    assert ok[0].price == 50 and ok[0].quantity == 100 and ok[0].side == "sell"


def test_malformed_bid_returns_error_without_crashing_connection():
    client = TestClient(app)
    created = client.post("/api/game", json={"preset": "classic", "rounds": 1}).json()
    gid, admin = created["id"], created["admin_token"]
    lec = client.websocket_connect(f"/ws/{gid}").__enter__()
    lec.send_json({"action": "join", "role": "lecturer", "token": admin})
    assert lec.receive_json()["type"] == "welcome"
    lec.receive_json()
    teams = []
    for i in range(2):
        w = client.websocket_connect(f"/ws/{gid}").__enter__()
        w.send_json({"action": "join", "role": "team", "name": f"T{i}"})
        assert w.receive_json()["type"] == "welcome"
        teams.append(w)
        _drain([lec, *teams])
    lec.send_json({"action": "start"})
    _drain([lec, *teams])
    lec.send_json({"action": "open_round"})
    _drain([lec, *teams])

    bad = teams[0]
    bad.send_json({"action": "bid", "segments": [{"price": 50}]})  # missing quantity
    assert bad.receive_json()["type"] == "error"  # graceful error, not a crash
    bad.send_json({"action": "bid", "segments": []})  # connection still usable
    assert bad.receive_json()["type"] == "state"

    for ws in (lec, *teams):
        ws.__exit__(None, None, None)


def test_technologies_endpoint_lists_default_capacities():
    from market.engine.tech import TECHS

    client = TestClient(app)
    techs = client.get("/api/technologies").json()
    assert {t["key"] for t in techs} == set(TECHS)
    coal = next(t for t in techs if t["key"] == "coal")
    assert coal["capacity"] == TECHS["coal"].capacity and "color" in coal


def test_create_game_applies_capacity_overrides():
    from market.server import GAMES

    client = TestClient(app)
    r = client.post("/api/game", json={"preset": "classic", "capacities": {"coal": 1000}}).json()
    game = GAMES[r["id"]].game
    assert game.capacity("coal") == 1000  # overridden
    assert game.capacity("gas") == 2200  # default kept


def test_create_game_rejects_bad_capacity():
    client = TestClient(app)
    assert client.post("/api/game", json={"capacities": {"coal": 0}}).status_code == 400
    assert client.post("/api/game", json={"capacities": {"coal": -5}}).status_code == 400
    assert client.post("/api/game", json={"capacities": {"nope": 100}}).status_code == 400


def test_show_final_toggles_flag():
    from market.engine.game import Game
    from market.engine.scenario import PRESETS
    from market.server import Room, Session, act

    room = Room(id="x", game=Game(scenarios=list(PRESETS["classic"])), admin_token="a")
    lec = Session(token="a", role="lecturer", name="L")
    act(room, lec, {"action": "show_final", "value": True})
    assert room.final is True
    act(room, lec, {"action": "show_final"})  # toggle off
    assert room.final is False


def test_standing_computes_final_stats():
    import pytest
    from market.engine.game import Team
    from market.server import _standing

    sold = Team("A", "coal", 1.0, 0.0)
    sold.profit, sold.energy, sold.ask_value = 10000, 200, 200 * 40
    s = _standing(sold, reveal=True)
    assert s["vwab"] == pytest.approx(40) and s["profit_per_mwh"] == pytest.approx(50)
    assert s["cost"] == 30  # coal base cost, shown only when roles are revealed

    idle = Team("B", "gas", 1.0, 0.0)  # never sold anything
    s2 = _standing(idle, reveal=True)
    assert s2["vwab"] is None and s2["profit_per_mwh"] is None
    assert _standing(sold, reveal=False)["cost"] is None  # hidden until roles revealed
