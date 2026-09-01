<script>
  import QR from './QR.svelte';

  let presets = $state({});
  let preset = $state('classic');
  let rounds = $state([]); // the editable scenario table
  let techs = $state([]); // technologies with editable installed capacity
  let created = $state(null);
  let error = $state(null);
  let joinCode = $state('');

  const blank = () => ({
    label: '',
    demand: 4000,
    wind: 30,
    sun: 30,
    co2_price: 0,
    gas_cost: 50, // gas's normal running cost; raise it to model a fuel shock
    coal_outage: 0,
    note: '',
  });

  const clone = (rows) => rows.map((r) => ({ ...r }));

  async function load() {
    presets = await (await fetch('/api/presets')).json();
    loadPreset('classic');
    techs = await (await fetch('/api/technologies')).json();
  }
  load();

  function loadPreset(name) {
    preset = name;
    rounds = clone(presets[name] || []);
  }

  const cols = [
    ['label', 'Label', 'text'],
    ['demand', 'Demand MWh', 'number'],
    ['wind', 'Wind %', 'number'],
    ['sun', 'Sun %', 'number'],
    ['co2_price', 'CO₂ €/t', 'number'],
    ['gas_cost', 'Gas €/MWh', 'number'],
    ['coal_outage', 'Coal outage MW', 'number'],
    ['note', 'Note (shown to players)', 'text'],
  ];

  async function createGame() {
    error = null;
    const capacities = Object.fromEntries(techs.map((t) => [t.key, Number(t.capacity)]));
    const res = await fetch('/api/game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenarios: $state.snapshot(rounds), capacities }),
    });
    if (res.ok) created = await res.json();
    else error = (await res.json()).detail || 'Could not create the game.';
  }

  const origin = () => location.origin;
  const studentLink = () => `${origin()}/g/${created.id}`;
  // token in the fragment (#), not the query, so it never reaches server logs
  const lecturerLink = () => `${origin()}/g/${created.id}#admin=${created.admin_token}`;

  function copy(text) {
    navigator.clipboard?.writeText(text);
  }
</script>

<div class="wrap">
  <h1>Electricity Market Game</h1>
  <p class="dim">
    Set up a market, share the links, and let teams bid their power plants into the merit order.
  </p>

  <div class="note">
    Based on the original paper role-play by
    <a href="https://www.martavictoria.org/" target="_blank" rel="noopener"><strong>Marta Victoria</strong></a>
    (DTU). Source and teaching materials:
    <a href="https://github.com/martavp/roleplay-electricity-market" target="_blank" rel="noopener">
      github.com/martavp/roleplay-electricity-market</a>.
  </div>

  <details class="card guide">
    <summary>How to run this game (for the lecturer)</summary>

    <p>
      This game lets students experience a wholesale electricity market <em>before</em> any theory
      is taught. Each team is given a power-generation technology and offers electricity into the
      market each round. The market clears where supply meets demand, and every team that clears is
      paid the single <strong>clearing price</strong> - regardless of the price it bid.
    </p>

    <h3>Setting up</h3>
    <ol>
      <li>
        Pick a scenario set and, if you wish, edit the rounds below. Each round is one instance of
        the market, representing a time of day with its own demand and weather (and, in some rounds,
        a CO<sub>2</sub> price or a fuel shock).
      </li>
      <li>
        Create the game. You receive two links: a <strong>student link</strong> to share widely, and
        a private <strong>lecturer link</strong> - open the latter on the projector.
      </li>
      <li>
        Students open the student link and enter a team name. Each team is randomly assigned a
        technology, with its own costs and constraints. Roles stay hidden from the other teams.
      </li>
    </ol>

    <h3>Running each round</h3>
    <ol start="4">
      <li>Announce the round's demand and weather (shown on your console), then open the round.</li>
      <li>
        Each team privately submits how much to offer and at what price. Offers can have several
        price steps (for example 200&nbsp;MW at 40&nbsp;&euro;/MWh, rising to more above
        80&nbsp;&euro;/MWh).
      </li>
      <li>
        Close the round to clear the market. Project the merit order - the offers stacked
        cheapest-first, meeting demand at the clearing price.
      </li>
      <li>
        Every team sees its own result - revenue (price &times; amount sold) minus its costs - and
        the leaderboard of cumulative profit.
      </li>
    </ol>

    <h3>Good to know</h3>
    <ul>
      <li>
        The game is deliberately <em>not</em> fair: technologies differ in cost and in how the
        weather affects them. That is the point.
      </li>
      <li>
        Renewables cost almost nothing to run but depend on wind and sun; conventional plants cost
        more but run at any time; storage (reservoir hydro and batteries) can buy cheap power to
        sell in a later round.
      </li>
      <li>
        If the offers cannot cover demand, the shortfall is shed at a very high price
        (3000&nbsp;&euro;/MWh) - a vivid scarcity signal.
      </li>
      <li>
        Roles are revealed on the leaderboard after each round; you can switch this off from the
        console to keep them secret until a final reveal.
      </li>
    </ul>

    <h3>Questions to discuss afterwards</h3>
    <ul>
      <li>Which technologies have the highest running costs? The highest opportunity costs (a hydro reservoir or a battery you could have saved for later)?</li>
      <li>What happens to the price when a lot of wind and solar are available?</li>
      <li>How did a CO<sub>2</sub> price or a fuel shock change who sets the price?</li>
      <li>Which common assumptions about electricity markets does this game make that do not hold in reality?</li>
    </ul>
  </details>

  {#if !created}
    <div class="card">
      <h2>Create a game (lecturer)</h2>
      <div class="row" style="align-items:flex-end;margin-bottom:0.8rem">
        <label style="flex:1">Start from a scenario set
          <select value={preset} onchange={(e) => loadPreset(e.currentTarget.value)}>
            <option value="classic">Classic - 5 rounds</option>
            <option value="extended">Extended + shocks - 7 rounds</option>
          </select>
        </label>
        <span class="dim">then edit the rounds below</span>
      </div>

      <div class="scroll">
        <table class="rounds">
          <thead>
            <tr><th>#</th>{#each cols as [, label]}<th>{label}</th>{/each}<th></th></tr>
          </thead>
          <tbody>
            {#each rounds as r, i}
              <tr>
                <td class="dim">{i + 1}</td>
                {#each cols as [key, , type]}
                  <td>
                    {#if type === 'number'}
                      <input type="number" bind:value={r[key]} />
                    {:else}
                      <input type="text" bind:value={r[key]} />
                    {/if}
                  </td>
                {/each}
                <td><button class="ghost" onclick={() => (rounds = rounds.filter((_, j) => j !== i))}
                  disabled={rounds.length === 1} aria-label="remove round">Remove</button></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="row" style="margin-top:0.8rem">
        <button class="ghost" onclick={() => (rounds = [...rounds, blank()])}>+ add round</button>
      </div>

      <h3 style="margin-top:1.4rem">Installed capacity (MW)</h3>
      <p class="dim" style="margin-top:0">
        The market total for each technology, split evenly among the teams that get it.
      </p>
      <div class="caps">
        {#each techs as t}
          <label>
            <span class="capname"><span class="dot" style="background:{t.color}"></span>{t.name}</span>
            <input type="number" min="0" bind:value={t.capacity} />
          </label>
        {/each}
      </div>

      <div class="row" style="margin-top:1.2rem">
        <span class="grow"></span>
        <button class="primary" onclick={createGame} disabled={!rounds.length}>Create game</button>
      </div>
      {#if error}<p class="neg">{error}</p>{/if}
    </div>
  {:else}
    <div class="card">
      <h2>Game <span class="dim">{created.id}</span> is ready</h2>
      <p><strong>Share with students</strong> - they can scan to join:</p>
      <div class="joinrow">
        <QR text={studentLink()} size={200} />
        <div class="grow">
          <div class="row">
            <input class="grow" readonly value={studentLink()} />
            <button onclick={() => copy(studentLink())}>Copy</button>
          </div>
        </div>
      </div>
      <p style="margin-top:1rem"><strong>Your lecturer console (keep private):</strong></p>
      <div class="row">
        <input class="grow" readonly value={lecturerLink()} />
        <button onclick={() => copy(lecturerLink())}>Copy</button>
      </div>
      <p style="margin-top:1rem">
        <a class="primary" href={lecturerLink()}>
          <button class="primary">Open lecturer console →</button>
        </a>
      </p>
    </div>
  {/if}

  <div class="card">
    <h2>Join a game (student)</h2>
    <div class="row">
      <input class="grow" bind:value={joinCode} placeholder="Game code, e.g. windy-grid-42" />
      <button onclick={() => joinCode && (location.href = `/g/${joinCode.trim()}`)}>Go</button>
    </div>
  </div>
</div>

<style>
  .guide {
    line-height: 1.6;
  }
  .guide summary {
    cursor: pointer;
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
  }
  .guide[open] summary {
    margin-bottom: 0.6rem;
  }
  .guide h3 {
    margin: 1.2rem 0 0.3rem;
  }
  .guide li {
    margin-bottom: 0.3rem;
  }
  .joinrow {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .caps {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.7rem 1rem;
  }
  .capname {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .dot {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    display: inline-block;
  }
  .scroll {
    overflow-x: auto;
  }
  .rounds {
    min-width: 720px;
  }
  .rounds th {
    font-size: 0.8rem;
    color: var(--dim);
    font-weight: 600;
    white-space: nowrap;
  }
  .rounds td {
    padding: 0.25rem 0.3rem;
  }
  .rounds input {
    min-height: 36px;
    padding: 0.35rem 0.45rem;
  }
  .rounds input[type='number'] {
    width: 5.5rem;
  }
  .rounds input[type='text'] {
    width: 12rem;
  }
</style>
