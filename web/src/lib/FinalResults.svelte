<script>
  let { board, me = null } = $props();

  const eur = (x) => (x / 1000).toLocaleString('en', { maximumFractionDigits: 1 }) + ' k€';
  const n0 = (x) => (x ?? 0).toLocaleString('en', { maximumFractionDigits: 0 });
  const perMwh = (x) => (x == null ? '–' : x.toFixed(1) + ' €/MWh');

  const winner = $derived(board[0]);
  const medals = ['1', '2', '3'];
</script>

<div class="card final">
  <div class="crown">Final results</div>
  {#if winner}
    <div class="winner">
      <div class="dim">Winner</div>
      <div class="wname">{winner.name}</div>
      {#if winner.tech}<span class="pill" style="background:{winner.color}">{winner.tech}</span>{/if}
      <div class="wprofit pos">{eur(winner.profit)}</div>
    </div>
  {/if}

  <div class="scroll">
    <table>
      <thead>
        <tr>
          <th>#</th><th>Team</th><th>Role</th>
          <th class="num">Profit</th>
          <th class="num">Energy sold</th>
          <th class="num">Base cost</th>
          <th class="num">Avg. ask</th>
          <th class="num">Profit / MWh</th>
        </tr>
      </thead>
      <tbody>
        {#each board as t, i}
          <tr class:top={i < 3} class:me={t.name === me}>
            <td>{medals[i] ?? i + 1}</td>
            <td>{t.name}</td>
            <td>{#if t.tech}<span class="pill" style="background:{t.color}">{t.tech}</span>{/if}</td>
            <td class="num {t.profit >= 0 ? 'pos' : 'neg'}">{eur(t.profit)}</td>
            <td class="num">{n0(t.energy)} MWh</td>
            <td class="num">{perMwh(t.cost)}</td>
            <td class="num">{perMwh(t.vwab)}</td>
            <td class="num">{perMwh(t.profit_per_mwh)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>

<style>
  .final {
    border-top: 5px solid var(--accent);
  }
  .crown {
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-size: clamp(1.6rem, 5vw, 2.2rem);
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 0.8rem;
  }
  .winner {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    flex-wrap: wrap;
    padding: 0.8rem 1rem;
    background: #f4f0fe;
    border-radius: 12px;
    margin-bottom: 1rem;
  }
  .wname {
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
  }
  .wprofit {
    margin-left: auto;
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
  }
  .scroll {
    overflow-x: auto;
  }
  tr.top td {
    font-weight: 600;
  }
  tr.me td {
    background: #f4f0fe;
  }
</style>
