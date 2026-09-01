<script>
  let { sc } = $props();
  const pct = (x) => `${Math.round((x ?? 0) * 100)}%`;
</script>

<div class="scenario">
  <div class="tag">This round</div>
  <h2>{sc.label}</h2>
  <p>{sc.note}</p>
  <div class="stats">
    <div><span>Electricity needed</span><strong>{sc.demand} MWh</strong></div>
    <div><span>Wind</span><strong>{pct(sc.availability.onshore)}</strong></div>
    <div><span>Sun</span><strong>{pct(sc.availability.solar)}</strong></div>
    {#if sc.co2_price}
      <div><span>Carbon price</span><strong>{sc.co2_price} €/tonne</strong></div>
    {/if}
  </div>
</div>

<style>
  .scenario {
    background: #0284c7;
    color: #fff;
    border-radius: var(--radius);
    padding: 1.4rem;
    margin-bottom: 1rem;
  }
  .tag {
    display: inline-block;
    background: rgba(255, 255, 255, 0.22);
    color: #fff;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  h2 {
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-size: clamp(1.6rem, 5vw, 2.2rem);
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0.4rem 0 0.3rem;
  }
  p {
    margin: 0 0 1rem;
    font-size: 1.05rem;
    max-width: 60ch;
  }
  .stats {
    display: flex;
    flex-wrap: wrap;
    gap: 1.6rem;
  }
  .stats div {
    display: flex;
    flex-direction: column;
  }
  .stats span {
    font-size: 0.8rem;
    color: rgba(255, 255, 255, 0.8);
  }
  .stats strong {
    font-family: 'Space Grotesk Variable', 'Inter', sans-serif;
    font-size: 1.3rem;
  }
</style>
