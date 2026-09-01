<script>
  import { net, send } from '../net.svelte.js';
  import Chart from './Chart.svelte';
  import Scenario from './Scenario.svelte';
  import FinalResults from './FinalResults.svelte';

  const d = $derived(net.data);
  const you = $derived(d.you);
  const card = $derived(you?.role_card);
  const showFinal = $derived(d.final && d.phase === 'FINISHED');

  const blank = () => [{ price: '', quantity: '' }];
  let sellSegs = $state(blank());
  let buySegs = $state(blank());
  let lastRound = -1;

  // Load the current round's submitted bid (split into sell/buy) when it changes.
  $effect(() => {
    if (d.round_no !== lastRound) {
      lastRound = d.round_no;
      const bid = you?.bid ?? [];
      const rows = (side) =>
        bid.filter((b) => b.side === side).map((b) => ({ price: b.price, quantity: b.quantity }));
      sellSegs = rows('sell').length ? rows('sell') : blank();
      buySegs = rows('buy').length ? rows('buy') : blank();
    }
  });

  const sum = (rows) => rows.reduce((s, x) => s + (Number(x.quantity) || 0), 0);
  const sellLimit = $derived(card?.sell_capacity ?? 0);
  const buyLimit = $derived(card?.charge_capacity ?? 0);
  const sellTotal = $derived(sum(sellSegs));
  const buyTotal = $derived(sum(buySegs));
  const sellOver = $derived(sellTotal > sellLimit + 1e-6);
  const buyOver = $derived(buyTotal > buyLimit + 1e-6);

  const eur = (x) => (x / 1000).toLocaleString('en', { maximumFractionDigits: 1 }) + ' k€';
  const n0 = (x) => (x ?? 0).toLocaleString('en', { maximumFractionDigits: 0 });

  const clean = (rows, side) =>
    rows
      .filter((s) => s.quantity !== '' && s.price !== '')
      .map((s) => ({ price: Number(s.price), quantity: Number(s.quantity), side }));

  function submit() {
    const payload = [...clean(sellSegs, 'sell'), ...(card.storage ? clean(buySegs, 'buy') : [])];
    send({ action: 'bid', segments: payload });
  }

  function constraints(cd) {
    const out = [];
    out.push(['Your maximum output', `${n0(cd.capacity_total)} MW`]);
    if (cd.cost !== undefined)
      out.push(['It costs you, per unit sold', `${cd.cost.toFixed(1)} €/MWh`]);
    if (cd.variable && cd.availability !== undefined)
      out.push(['Usable right now (weather)', `${Math.round(cd.availability * 100)}% of your output`]);
    if (cd.sell_capacity !== undefined)
      out.push(['You can sell this round up to', `${n0(cd.sell_capacity)} MW`]);
    if (cd.storage) {
      out.push(['Energy in store', `${n0(cd.soc)} of ${n0(cd.energy)} MWh`]);
      out.push(['Most you can charge at once', `${n0(cd.charge_power)} MW`]);
      out.push(['Round-trip efficiency', `${Math.round(cd.efficiency * 100)}%`]);
    }
    if (cd.emission_factor > 0)
      out.push(['CO₂ released per unit', `${cd.emission_factor} tonnes/MWh`]);
    out.push(['You may bid between', `${cd.floor} and ${cd.cap} €/MWh`]);
    return out;
  }
</script>

<div class="wrap">
  {#if showFinal}
    <FinalResults board={d.leaderboard} me={you?.name} />
  {:else}
  <div class="row" style="margin-bottom:0.6rem">
    <span class="grow dim">{you?.name}</span>
    <span class="dim">Round {d.round_no || '-'} / {d.n_rounds}</span>
  </div>

  <!-- role hero -->
  {#if card}
    <div class="card hero" style="--role:{card.color}">
      <div class="dim">Your technology</div>
      <div class="rolename" style="color:{card.color}">{card.name}</div>
      <p style="margin:0.2rem 0 1rem">{card.blurb}</p>
      <div class="clist">
        {#each constraints(card) as [k, v]}
          <div class="citem"><span class="dim">{k}</span><strong>{v}</strong></div>
        {/each}
      </div>
    </div>
  {:else}
    <div class="card"><p class="dim">Waiting for the lecturer to assign roles and start the game.</p></div>
  {/if}

  <div class="card metrics">
    <div><div class="dim">Cumulative profit</div>
      <div class="big {you?.profit >= 0 ? 'pos' : 'neg'}">{eur(you?.profit ?? 0)}</div></div>
    <div><div class="dim">Energy sold</div>
      <div class="big">{n0(you?.energy ?? 0)}<span class="unit"> MWh</span></div></div>
  </div>

  {#if d.scenario && d.phase !== 'LOBBY'}
    <Scenario sc={d.scenario} />
  {/if}

  {#if d.phase === 'LOBBY' && card}
    <div class="card"><p class="dim">Roles are set. Waiting for the lecturer to open round 1.</p></div>
  {/if}

  <!-- bidding -->
  {#if d.phase === 'BIDDING' && card}
    <div class="card">
      <div class="row" style="margin-bottom:0.8rem">
        <span class="chip">Your bids</span>
        <span class="grow"></span>
        {#if you.submitted}<span class="tag" style="background:#dcfce7;color:#166534">Submitted</span>{/if}
      </div>

      {#if card.storage}
        <h3>Sell (discharge)</h3>
        <p class="dim" style="margin-top:0">
          It costs you <strong>{card.cost?.toFixed(1)} €/MWh</strong> to produce. State the
          <strong>lowest</strong> price you will accept, for up to
          <strong>{n0(sellLimit)} MW</strong>.
        </p>
      {/if}
      <div class="stack">
        {#each sellSegs as s, i}
          <div class="seg">
            <label>Price €/MWh<input type="number" inputmode="decimal" min={card.floor} max={card.cap} bind:value={s.price} /></label>
            <label>Quantity MW<input type="number" inputmode="numeric" min="0" bind:value={s.quantity} /></label>
            <button class="ghost" onclick={() => (sellSegs = sellSegs.filter((_, j) => j !== i))} disabled={sellSegs.length === 1}>Remove</button>
          </div>
        {/each}
      </div>
      <div class="row" style="margin-top:0.6rem">
        <button class="ghost" onclick={() => (sellSegs = [...sellSegs, { price: '', quantity: '' }])}>+ price step</button>
        <span class="grow" style="text-align:right" class:neg={sellOver}>{n0(sellTotal)} / {n0(sellLimit)} MW</span>
      </div>

      {#if card.storage}
        <h3 style="margin-top:1.3rem">Buy to charge (optional)</h3>
        <p class="dim" style="margin-top:0">
          State the <strong>highest</strong> price you will pay to store energy for a later round.
          You can charge up to <strong>{n0(buyLimit)} MW</strong>. Your buy price must be below
          your sell price, so only one side can happen in a round.
        </p>
        <div class="stack">
          {#each buySegs as s, i}
            <div class="seg">
              <label>Price €/MWh<input type="number" inputmode="decimal" min={card.floor} max={card.cap} bind:value={s.price} /></label>
              <label>Quantity MW<input type="number" inputmode="numeric" min="0" bind:value={s.quantity} /></label>
              <button class="ghost" onclick={() => (buySegs = buySegs.filter((_, j) => j !== i))} disabled={buySegs.length === 1}>Remove</button>
            </div>
          {/each}
        </div>
        <div class="row" style="margin-top:0.6rem">
          <button class="ghost" onclick={() => (buySegs = [...buySegs, { price: '', quantity: '' }])}>+ price step</button>
          <span class="grow" style="text-align:right" class:neg={buyOver}>{n0(buyTotal)} / {n0(buyLimit)} MW</span>
        </div>
      {/if}

      <button class="primary" style="width:100%;margin-top:1rem" onclick={submit}
        disabled={sellOver || buyOver || (sellTotal === 0 && buyTotal === 0)}>
        {you.submitted ? 'Update bid' : 'Submit bid'}
      </button>
    </div>
  {/if}

  <!-- result -->
  {#if (d.phase === 'CLEARED' || d.phase === 'FINISHED') && you?.last?.price !== undefined}
    <div class="card">
      <h2>Your result - round {d.round_no}</h2>
      <table>
        <tbody>
          <tr><td>Clearing price</td><td class="num">{you.last.price.toFixed(1)} €/MWh</td></tr>
          {#if you.last.sold > 0}
            <tr><td>Sold</td><td class="num">{n0(you.last.sold)} MWh</td></tr>
            <tr><td>Revenue = price × sold</td><td class="num pos">{eur(you.last.revenue)}</td></tr>
            <tr><td>Generation cost</td><td class="num neg">−{eur(you.last.cost)}</td></tr>
          {/if}
          {#if you.last.charged > 0}
            <tr><td>Charged (stored for later)</td><td class="num">{n0(you.last.charged)} MWh</td></tr>
            <tr><td>Paid to charge</td><td class="num neg">−{eur(you.last.paid)}</td></tr>
          {/if}
          <tr><td><strong>Round profit</strong></td>
            <td class="num {you.last.delta >= 0 ? 'pos' : 'neg'}"><strong>{eur(you.last.delta)}</strong></td></tr>
        </tbody>
      </table>
    </div>
  {/if}

  {#if d.clearing && (d.phase === 'CLEARED' || d.phase === 'FINISHED')}
    <div class="card">
      <h2>Merit order</h2>
      <Chart clearing={d.clearing} />
    </div>
  {/if}

  {#if d.phase === 'CLEARED' || d.phase === 'FINISHED'}
    <div class="card">
      <h2>{d.phase === 'FINISHED' ? 'Final standings' : 'Leaderboard'}</h2>
      <table>
        <thead><tr><th>#</th><th>Team</th><th>Role</th><th class="num">Profit</th><th class="num">Energy</th></tr></thead>
        <tbody>
          {#each d.leaderboard as t, i}
            <tr style={t.name === you?.name ? 'font-weight:700' : ''}>
              <td>{i + 1}</td><td>{t.name}</td>
              <td>{#if t.tech}<span class="pill" style="background:{t.color}">{t.tech}</span>{/if}</td>
              <td class="num {t.profit >= 0 ? 'pos' : 'neg'}">{eur(t.profit)}</td>
              <td class="num dim">{n0(t.energy)} MWh</td></tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
  {/if}
</div>

<style>
  .chip {
    display: inline-block;
    background: var(--accent);
    color: #fff;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .hero {
    border-top: 5px solid var(--role);
  }
  .rolename {
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-size: clamp(2rem, 9vw, 3rem);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.05;
    margin: 0.1rem 0 0.3rem;
  }
  .clist {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.7rem 1.4rem;
  }
  .citem {
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--line);
    padding-top: 0.4rem;
  }
  .seg {
    display: flex;
    gap: 0.6rem;
    align-items: flex-end;
  }
  .seg label {
    flex: 1;
  }
  .seg button {
    flex: 0 0 auto;
  }
</style>
