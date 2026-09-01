<script>
  // Interactive merit-order chart (plain DOM, no SVG): supply staircase meeting
  // the demand curve. Battery/pumping charge bids are drawn as extra demand to
  // the right of the inelastic demand line. Hover (or tap) any bar for details.
  let { clearing } = $props();

  const c = $derived(clearing);
  const supply = $derived(withCum(c.supply));
  const charge = $derived(withCum(c.demand_bids ?? [], c.demand));
  const totalSupply = $derived(sum(c.supply, 'quantity'));
  const totalCharge = $derived(sum(c.demand_bids ?? [], 'quantity'));

  const prices = $derived([...c.supply, ...(c.demand_bids ?? [])].map((b) => b.price));
  const xMax = $derived(Math.max(totalSupply, c.demand + totalCharge, 1) * 1.04);
  // Scale to the clearing price, not the tallest bid, so one very high offer
  // does not squash the picture; taller bars simply clamp to the top edge.
  const yMax = $derived(Math.max(200, c.price * 1.15, ...prices.filter((p) => p <= 200)) + 1);
  const yMin = $derived(Math.min(0, ...prices));

  const priceTicks = $derived(ticks(yMin, yMax, niceStep(yMax - yMin)));
  const mwTicks = $derived(ticks(0, xMax, niceStep(xMax)));

  let tip = $state(null);

  function withCum(arr, start = 0) {
    let x = start;
    return arr
      .filter((b) => b.quantity > 0)
      .map((b) => {
        const o = { ...b, x0: x, x1: x + b.quantity, xc: x + (b.cleared ?? 0) };
        x += b.quantity;
        return o;
      });
  }
  const sum = (arr, k) => arr.reduce((s, b) => s + b[k], 0);
  const px = (mw) => (mw / xMax) * 100;
  const pos = (p) => ((Math.max(yMin, Math.min(p, yMax)) - yMin) / (yMax - yMin)) * 100;
  const zero = $derived(pos(0));
  // vertical geometry of a bar drawn between its price and the zero line
  const barLo = (p) => Math.min(pos(p), zero);
  const barH = (p) => Math.abs(pos(p) - zero);

  function ticks(lo, hi, step) {
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(v);
    return out;
  }
  function niceStep(span) {
    const raw = span / 5;
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    return Math.max(pow, Math.round(raw / pow) * pow);
  }

  function show(e, b, kind) {
    const box = e.currentTarget.closest('.plot').getBoundingClientRect();
    tip = {
      x: e.clientX - box.left,
      y: e.clientY - box.top,
      lines: [
        `${b.team} - ${b.tech}`,
        `${kind} ${fmt(b.quantity)} MW at ${b.price.toFixed(0)} €/MWh`,
        `cleared ${fmt(b.cleared)} MW`,
      ],
      color: b.color,
    };
  }
  const fmt = (x) => (x ?? 0).toFixed(0);
  const clearingLabel = $derived(
    c.scarce ? `${c.price.toFixed(0)} €/MWh - load shedding` : `${c.price.toFixed(1)} €/MWh`
  );
</script>

<div class="plot" role="figure" aria-label="merit order chart" onpointerleave={() => (tip = null)}>
  <div class="area">
    {#each priceTicks as p}
      <div class="grid" class:zero={p === 0} style="bottom:{pos(p)}%"></div>
      <div class="ylab" style="bottom:{pos(p)}%">{p}</div>
    {/each}
    {#each mwTicks as m}
      <div class="xlab" style="left:{px(m)}%">{m}</div>
    {/each}

    <!-- supply staircase -->
    {#each supply as b}
      <div class="bar" style="left:{px(b.x0)}%;width:{px(b.quantity)}%;bottom:{barLo(b.price)}%;height:{barH(b.price)}%;background:{b.color};opacity:.28"
        onpointerenter={(e) => show(e, b, 'offer')} onpointermove={(e) => show(e, b, 'offer')}
        role="img" aria-label="{b.team} offer"></div>
      {#if b.cleared > 0}
        <div class="bar" style="left:{px(b.x0)}%;width:{px(b.cleared)}%;bottom:{barLo(b.price)}%;height:{barH(b.price)}%;background:{b.color}"
          onpointerenter={(e) => show(e, b, 'offer')} onpointermove={(e) => show(e, b, 'offer')}
          role="img" aria-label="{b.team} cleared"></div>
      {/if}
    {/each}

    <!-- charging bids = extra demand to the right of the demand line -->
    {#each charge as b}
      <div class="bar dash" style="left:{px(b.x0)}%;width:{px(b.quantity)}%;bottom:{barLo(b.price)}%;height:{barH(b.price)}%;border-color:{b.color};color:{b.color}"
        onpointerenter={(e) => show(e, b, 'charge')} onpointermove={(e) => show(e, b, 'charge')}
        role="img" aria-label="{b.team} charge"></div>
    {/each}

    <!-- inelastic demand line -->
    <div class="demand" style="left:{px(c.demand)}%"></div>

    <!-- clearing lines -->
    <div class="clear-h" style="bottom:{pos(c.price)}%"></div>
    <div class="clear-v" style="left:{px(c.volume)}%"></div>
    <div class="clear-dot" style="left:{px(c.volume)}%;bottom:{pos(c.price)}%"></div>
    <div class="clear-lab" style="bottom:{pos(c.price)}%">{clearingLabel}</div>
  </div>

  <div class="axisx">cumulative capacity (MW)</div>
  <div class="axisy">price (€/MWh)</div>

  {#if tip}
    <div class="tip" style="left:{tip.x}px;top:{tip.y}px;border-color:{tip.color}">
      {#each tip.lines as l}<div>{l}</div>{/each}
    </div>
  {/if}
</div>

<div class="legend">
  <span class="demand-key">demand line</span>
  <span class="charge-key">charge bid</span>
  <span class="dim">faded = offered, solid = cleared</span>
</div>

<style>
  .plot {
    position: relative;
    height: 340px;
    padding: 8px 12px 30px 44px;
  }
  @media (max-width: 560px) {
    .plot {
      height: 260px;
      padding-left: 36px;
    }
  }
  .area {
    position: absolute;
    inset: 8px 12px 30px 44px;
  }
  .grid {
    position: absolute;
    left: 0;
    right: 0;
    height: 1px;
    background: var(--line);
  }
  .grid.zero {
    background: #c7cbd1;
    height: 1.5px;
  }
  .ylab {
    position: absolute;
    left: -40px;
    transform: translateY(50%);
    font-size: 13px;
    color: var(--dim);
  }
  .xlab {
    position: absolute;
    bottom: -20px;
    transform: translateX(-50%);
    font-size: 13px;
    color: var(--dim);
  }
  .bar {
    position: absolute;
    bottom: 0;
    box-shadow: inset 0 0 0 0.5px #fff;
    cursor: pointer;
  }
  .bar.dash {
    background: transparent;
    border: 1.5px dashed currentColor;
    opacity: 0.85;
  }
  .demand {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 0;
    border-left: 2px dashed var(--ink);
  }
  .clear-h {
    position: absolute;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent);
  }
  .clear-v {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--accent);
    opacity: 0.5;
  }
  .clear-dot {
    position: absolute;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    background: var(--accent);
    transform: translate(-50%, 50%);
    box-shadow: 0 0 0 3px #fff;
  }
  .clear-lab {
    position: absolute;
    right: 2px;
    transform: translateY(-115%);
    font-size: 14px;
    font-weight: 700;
    color: var(--accent);
  }
  .axisx {
    position: absolute;
    bottom: 2px;
    left: 44px;
    right: 12px;
    text-align: center;
    font-size: 13px;
    color: var(--dim);
  }
  .axisy {
    position: absolute;
    left: -6px;
    top: 50%;
    transform: rotate(-90deg);
    transform-origin: left;
    font-size: 13px;
    color: var(--dim);
    white-space: nowrap;
  }
  .tip {
    position: absolute;
    transform: translate(12px, -50%);
    background: var(--ink);
    color: #fff;
    padding: 0.4rem 0.6rem;
    border-radius: 8px;
    border-left: 4px solid;
    font-size: 14px;
    pointer-events: none;
    white-space: nowrap;
    z-index: 5;
  }
  .legend {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    font-size: 14px;
    color: var(--dim);
    margin-top: 0.4rem;
  }
  .demand-key::before {
    content: '';
    display: inline-block;
    width: 16px;
    border-top: 2px dashed var(--ink);
    margin-right: 5px;
    vertical-align: middle;
  }
  .charge-key::before {
    content: '';
    display: inline-block;
    width: 14px;
    height: 9px;
    border: 1.5px dashed var(--dim);
    margin-right: 5px;
    vertical-align: middle;
  }
</style>
