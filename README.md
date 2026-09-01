# ⚡ Electricity Market Game

An online, interactive electricity-market role-play for teaching. Student teams
run power plants (coal, gas, hydro, wind, solar, batteries), bid them into a
wholesale market each round, and watch the **merit order** clear. It is designed
to be played *before* any theory is taught, to build intuition about marginal
costs, price formation, scarcity, and storage arbitrage.

Based on the original paper role-play by
[Marta Victoria](https://www.martavictoria.org/) (DTU) -
[github.com/martavp/roleplay-electricity-market](https://github.com/martavp/roleplay-electricity-market)
(see also `Roleplay_electricity_market.tex`).

## How it plays

- The **lecturer** creates a game, shares a link, and controls the rounds
  (open bidding → close & clear the market). A projector view shows the merit
  order, clearing price, volume, emissions, and the leaderboard.
- **Student teams** join with just a team name (no login). Each team is randomly
  assigned a technology with its own costs and constraints, and submits a
  (possibly multi-step) bid each round without seeing the others' bids.
- Teams are paid the single **clearing price** for everything that clears. They
  compete for the highest cumulative profit. The game is deliberately *not* fair
  - different technologies have very different positions in the merit order.

### What scales with class size

The market's total capacity per technology is fixed, so the well-tested demand
scenarios stay meaningful for any number of teams. When several teams share a
technology, its capacity is split equally between them. With six or more teams
every technology is represented; extra teams split the largest ones.

### Model highlights

- **Merit order** with uniform (pay-as-cleared) pricing and partial dispatch of
  the marginal bid. If two teams set the price with equal bids, the remaining
  demand is split between them **pro rata** to the quantities they bid there.
- **Bids** may be negative (e.g. to avoid being switched off) down to
  -500 EUR/MWh, and range up to the value of lost load, 3000 EUR/MWh - no bid can
  sensibly exceed that, since above it shedding the load is cheaper.
- **Load shedding**: if the offered supply cannot meet demand, the missing load
  is shed at the value of lost load (3000 EUR/MWh) and everyone who runs is paid
  that price - a dramatic scarcity signal.
- **Roles**: while bidding, students see only their own technology and
  constraints. After each round clears, every team's technology is resolved on
  the leaderboard, colour-coded. The lecturer can toggle this reveal off (to keep
  roles secret until a final reveal) or on at any time; the lecturer always sees
  all roles.
- **CO2 price** raises the effective cost of coal and gas (`cost = fuel +
  CO2_price x emission_factor`); a shock can flip coal and gas in the order.
- **Storage** (reservoir hydro, pumped hydro, batteries) can *buy* electricity
  to charge and *sell* it later - a two-sided market - with an energy budget and
  state of charge tracked across rounds. Charge bids appear in the demand curve.
- **Interactive merit-order chart** on both the projector and the team screens:
  hover (or tap) any bid to see its team, technology, price, and volume.

## Architecture

Three strictly separated layers (inspired by the sibling `doppelkopf` project):

| Layer | Location | Responsibility |
|---|---|---|
| **Engine** | `server/market/engine/` | Pure simulation: technologies, scenarios, market clearing, profits, storage. No I/O, fully pytest-tested. |
| **Server** | `server/market/server.py` | FastAPI + WebSockets. Holds games in RAM, sends each client a personalized state. |
| **UI** | `web/` | Svelte 5 + Vite. Lecturer console, team bidding, results. |

No persistence: a server restart clears all games. Reconnect works via a token
(`sessionStorage`) or, failing that, the team name.

## Run locally

Prerequisites: [uv](https://docs.astral.sh/uv/) and Node >= 20.

```bash
# 1. Backend (terminal 1)
uv sync
uv run uvicorn market.server:app --app-dir server --reload --port 8000

# 2. Frontend dev server (terminal 2)
cd web
npm install
npm run dev          # -> http://localhost:5173 (proxies /ws and /api to the backend)
```

Open `http://localhost:5173`, create a game, and open the **lecturer link** in
one tab and the **student link** in several other tabs (each tab is one team).

Without the dev server (this is also how it runs in production):

```bash
cd web && npm run build && cd ..
uv run uvicorn market.server:app --app-dir server --port 8000
# -> http://localhost:8000
```

## Tests, linting, typing

```bash
uv run pytest              # engine + server tests
uv run ruff check server tests
uv run ruff format server tests
uv run mypy server
```

## Deploy on a Fedora server

The app is a **single process**: `uvicorn` serves the API, the WebSocket, and the
built frontend on `127.0.0.1:8000` (localhost only). In front of it, **Caddy**
handles HTTPS and routes your subdomain to it - and it happily fronts more
services later, each as one more block in its config. **systemd** runs the app,
as a throwaway unprivileged user it creates on the fly (`DynamicUser`), so
there's no service account to manage.

The example uses `marketgame.fneum.org` - substitute your own subdomain.

### 1. Point the subdomain at the server

In the DNS settings for `fneum.org`, add one record. Providers label the fields
slightly differently; the mapping is:

| Field (common labels)        | Value                          |
|------------------------------|--------------------------------|
| **Type**                     | `A`                            |
| **Name** / Host / Subdomain  | `marketgame`                   |
| **Value** / Points to / Target | your server's public IPv4, e.g. `203.0.113.42` |
| **TTL**                      | leave default (or `300` while testing) |

Notes:

- **Name field:** most providers want just the label `marketgame` and append
  `.fneum.org` automatically; a few want the full `marketgame.fneum.org`. (`@`
  means the bare `fneum.org`, which you don't want here.)
- Find the server's IP with `curl -4 ifconfig.me` on the server. If it also has
  an IPv6 address, add a second record of **Type `AAAA`**, same Name, with that
  IPv6 value.
- **Alternative:** instead of an A record you can use a **CNAME** with Name
  `marketgame` and Value `fneum.org` - but only if `fneum.org` itself already
  points at this server.
- **Cloudflare:** if your DNS is on Cloudflare, set the record to **DNS only**
  (grey cloud, proxy off) so Caddy can obtain the certificate and WebSockets pass
  through cleanly.

Do this first, so Caddy can obtain a certificate in step 4. Check it resolves
with `ping marketgame.fneum.org` (DNS can take a few minutes to propagate).

### 2. Install the tools, copy the code, and build

On the server (as root), install what's needed:

```bash
dnf install -y git nodejs npm caddy uv rsync   # if `uv` isn't packaged: curl -LsSf https://astral.sh/uv/install.sh | sh
```

Get the code into `/opt/electricity-market-game`, either from a git remote:

```bash
git clone <your-repo-url> /opt/electricity-market-game
```

**or**, if the code isn't in a git remote, copy it straight from your laptop with
`rsync` (run this on your laptop, from the project directory). It uses the repo's
`.rsync-exclude` file to skip the virtualenv, `node_modules`, build output and
caches:

```bash
rsync -av --delete --exclude-from=.rsync-exclude ./ root@<ip>:/opt/electricity-market-game/
```

(`--delete` keeps the server copy tidy on repeat syncs; the excluded build dirs
already on the server - `.venv`, `web/dist`, `node_modules` - are left untouched.)

Then build, on the server:

```bash
cd /opt/electricity-market-game
uv sync --no-dev
(cd web && npm install && npm run build)   # builds the frontend into web/dist
```

### 3. Run it with systemd

Create `/etc/systemd/system/market.service`:

```ini
[Unit]
Description=Electricity Market Game
After=network.target

[Service]
WorkingDirectory=/opt/electricity-market-game
ExecStart=/opt/electricity-market-game/.venv/bin/uvicorn market.server:app --app-dir server --host 127.0.0.1 --port 8000
Restart=always
# a fresh unprivileged user per start; the app writes nothing to disk
DynamicUser=yes
ProtectSystem=strict
PrivateTmp=yes
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now market
systemctl status market                    # should say "active (running)"
curl -s localhost:8000/ | head -c 60       # a quick sanity check - prints HTML
```

### 4. Put it online with HTTPS (Caddy)

Fedora's default Caddyfile ends with `import Caddyfile.d/*.caddyfile`, so the tidy
way to add a site is a file of its own - the main Caddyfile stays untouched:

```bash
cat > /etc/caddy/Caddyfile.d/marketgame.caddyfile <<'EOF'
marketgame.fneum.org {
    reverse_proxy 127.0.0.1:8000
}
EOF
```

If the default `http:// { … }` welcome-page block is still in `/etc/caddy/Caddyfile`,
delete it - as a catch-all on port 80 it can suppress the automatic HTTP→HTTPS
redirect for your site. Then start Caddy:

```bash
systemctl enable --now caddy      # or: systemctl reload caddy, if already running
```

Caddy fetches a Let's Encrypt certificate automatically on the first request.
Ports 80/443 must be reachable: Fedora Cloud images usually run no host firewall
(if `firewall-cmd` says "FirewallD is not running", nothing to do), but if one is
active, open them - and open them in any cloud firewall in front of the VM too:

```bash
firewall-cmd --permanent --add-service=http --add-service=https && firewall-cmd --reload
```

The game is then live at `https://marketgame.fneum.org`; the student link is
`https://marketgame.fneum.org/g/<id>` and your private lecturer link is
`https://marketgame.fneum.org/g/<id>#admin=<token>`.

**Adding another service later** is the same pattern: run it on its own port and
drop another file in `Caddyfile.d/`, then `systemctl reload caddy`:

```bash
cat > /etc/caddy/Caddyfile.d/otherapp.caddyfile <<'EOF'
otherapp.fneum.org {
    reverse_proxy 127.0.0.1:8001
}
EOF
```

### 5. Update later

Refresh the code - either `cd /opt/electricity-market-game && git pull` on the
server, or rsync again from your laptop:

```bash
rsync -av --delete --exclude-from=.rsync-exclude ./ root@<ip>:/opt/electricity-market-game/
```

Then rebuild and restart, on the server:

```bash
cd /opt/electricity-market-game
uv sync --no-dev
(cd web && npm install && npm run build)
systemctl restart market
```

### If something misbehaves

- **App won't start:** `journalctl -u market -e` shows the Python error.
- **502 Bad Gateway:** Caddy is up but can't reach the app - check
  `systemctl status market`. On SELinux also run
  `setsebool -P httpd_can_network_connect 1`.
- **Certificate didn't issue:** the subdomain must resolve to this server and
  ports 80/443 must be open (host firewall *and* any cloud firewall).

### Security notes

- **Runs unprivileged.** `DynamicUser` gives the service a throwaway user each
  start, with `ProtectSystem`/`PrivateTmp`/`NoNewPrivileges`; the app holds all
  state in RAM and writes nothing to disk.
- **HTTPS everywhere.** Caddy encrypts the WebSocket (`wss://`) too. The lecturer
  token rides in the URL *fragment* (`#admin=...`), which browsers never send to
  the server, so it stays out of access logs. Still treat the lecturer link as a
  password: share it privately, the student link publicly.
- **Game creation is open** by design; games live in RAM and auto-expire after
  24 h of inactivity.
- **No accounts, no personal data.** Teams are just names; a restart clears all.

## Discussion questions (after playing)

- Which technologies have the highest marginal costs? The highest opportunity
  costs (hydro reservoir, storage)?
- What does abundant wind and solar do to the market price?
- How did the CO2 price or the gas shock reorder the merit order?
- Which market assumptions here do not reflect reality?
