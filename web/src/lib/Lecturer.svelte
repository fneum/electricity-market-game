<script>
  import { net, send } from '../net.svelte.js';
  import Chart from './Chart.svelte';
  import Scenario from './Scenario.svelte';
  import QR from './QR.svelte';
  import FinalResults from './FinalResults.svelte';

  const d = $derived(net.data);
  const assigned = $derived(d.teams.length > 0 && d.teams.every((t) => t.tech));
  const submitted = $derived(d.teams.filter((t) => t.submitted).length);
  const finished = $derived(d.phase === 'FINISHED');
  const studentLink = $derived(`${location.origin}/g/${d.game}`);

  const eur = (x) => (x / 1000).toLocaleString('en', { maximumFractionDigits: 0 }) + ' k€';
  const n0 = (x) => (x ?? 0).toLocaleString('en', { maximumFractionDigits: 0 });
</script>

<div class="wrap wide">
  <div class="row">
    <h1 class="grow">Lecturer console <span class="dim" style="font-weight:400">{d.game}</span></h1>
    <span class="dim">Round {d.round_no} / {d.n_rounds} · {d.phase}</span>
  </div>

  <div class="card row">
    {#if !assigned}
      <button class="primary" onclick={() => send({ action: 'start' })} disabled={d.teams.length < 2}>
        Assign roles &amp; lock lobby ({d.teams.length} teams)
      </button>
      <span class="dim">Students scan the code below to join.</span>
    {:else if d.phase === 'BIDDING'}
      <button class="primary" onclick={() => send({ action: 'close_round' })}>
        Close round &amp; clear market
      </button>
      <span class="dim">{submitted} / {d.teams.length} teams submitted</span>
    {:else if d.round_no < d.n_rounds}
      <button class="primary" onclick={() => send({ action: 'open_round' })}>
        Open round {d.round_no + 1}
      </button>
      <button class="ghost" onclick={() => send({ action: 'reset' })}>Reset game</button>
    {:else}
      <button class="primary" onclick={() => send({ action: 'show_final', value: !d.final })}>
        {d.final ? 'Back to details' : 'Show final results'}
      </button>
      <button class="ghost" onclick={() => send({ action: 'reset' })}>Reset game</button>
    {/if}
    <span class="grow"></span>
    <button class="ghost" onclick={() => send({ action: 'reveal', value: !d.reveal })}>
      {d.reveal ? 'Hide roles from students' : 'Reveal roles to students'}
    </button>
  </div>

  {#if d.final && finished}
    <FinalResults board={d.leaderboard} />
  {:else}
    {#if !assigned}
      <div class="card joincard">
        <div>
          <h2>Join this game</h2>
          <p class="dim">Scan the code, or go to:</p>
          <p class="joinlink">{studentLink}</p>
          <p class="dim">{d.teams.length} team{d.teams.length === 1 ? '' : 's'} joined so far.</p>
        </div>
        <QR text={studentLink} size={240} />
      </div>
    {/if}

    {#if d.scenario && d.phase !== 'LOBBY'}
      <Scenario sc={d.scenario} />
    {/if}

    {#if d.clearing && (d.phase === 'CLEARED' || finished)}
      <div class="card">
        <h2>Market clearing - round {d.round_no}</h2>
        <div class="metrics" style="margin-bottom:1rem">
          <div><div class="dim">Clearing price</div><div class="big">{d.clearing.price.toFixed(1)}<span class="unit"> €/MWh</span></div></div>
          <div><div class="dim">Volume</div><div class="big">{n0(d.clearing.volume)}<span class="unit"> MWh</span></div></div>
          <div><div class="dim">Emissions</div><div class="big">{n0(d.clearing.emissions)}<span class="unit"> tCO₂</span></div></div>
          {#if d.clearing.scarce}
            <div><div class="dim">Load shed</div><div class="big neg">{n0(d.clearing.unserved)}<span class="unit"> MWh</span></div></div>
          {/if}
        </div>
        <Chart clearing={d.clearing} />
      </div>
    {/if}

    <div class="row" style="align-items:flex-start">
      <div class="card grow">
        <h2>Leaderboard</h2>
        <table>
          <thead><tr><th>#</th><th>Team</th><th>Role</th><th class="num">Profit</th><th class="num">Energy</th></tr></thead>
          <tbody>
            {#each d.leaderboard as t, i}
              <tr><td>{i + 1}</td><td>{t.name}</td>
                <td>{#if t.tech}<span class="pill" style="background:{t.color}">{t.tech}</span>{:else}<span class="dim">hidden</span>{/if}</td>
                <td class="num {t.profit >= 0 ? 'pos' : 'neg'}">{eur(t.profit)}</td>
                <td class="num dim">{n0(t.energy)} MWh</td></tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="card grow">
        <h2>Teams &amp; roles</h2>
        <table>
          <thead><tr><th>Team</th><th>Technology</th><th class="num">Bid?</th></tr></thead>
          <tbody>
            {#each d.teams as t}
              <tr><td>{t.name}</td>
                <td>{#if t.tech}<span class="pill" style="background:{t.color}">{t.tech}</span>{:else}<span class="dim">-</span>{/if}</td>
                <td class="num">{t.submitted ? 'yes' : ''}</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>

<style>
  .joincard {
    display: flex;
    gap: 1.5rem;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .joinlink {
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-size: clamp(1.3rem, 3vw, 2rem);
    font-weight: 700;
    color: var(--accent);
    word-break: break-all;
    margin: 0.2rem 0;
  }
</style>
