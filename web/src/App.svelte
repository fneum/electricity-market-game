<script>
  import { net, connect } from './net.svelte.js';
  import Start from './lib/Start.svelte';
  import Lecturer from './lib/Lecturer.svelte';
  import Team from './lib/Team.svelte';

  const gameId = location.pathname.startsWith('/g/')
    ? decodeURIComponent(location.pathname.slice(3))
    : null;
  // the lecturer token lives in the URL fragment (#admin=...), which browsers
  // never send to the server, so it stays out of access logs and referrers.
  const adminToken = new URLSearchParams(location.hash.slice(1)).get('admin');

  let name = $state(localStorage.getItem('emg-name') || '');
  let joined = $state(false);

  if (gameId && adminToken) {
    connect(gameId, { role: 'lecturer', token: adminToken });
  }

  function joinTeam(e) {
    e.preventDefault();
    if (!name.trim()) return;
    localStorage.setItem('emg-name', name.trim());
    connect(gameId, { role: 'team', name: name.trim() });
    joined = true;
  }
</script>

{#if net.error}
  <div class="banner err">{net.error}</div>
{/if}

{#if !gameId}
  <Start />
{:else if adminToken}
  {#if net.data}
    <Lecturer />
  {:else}
    <div class="center dim">Connecting …</div>
  {/if}
{:else if !joined || net.rejected}
  <div class="center">
    <form class="card" style="min-width:320px" onsubmit={joinTeam}>
      <h1>Join the market</h1>
      <p class="dim">Game <strong>{gameId}</strong></p>
      {#if net.rejected}
        <p class="neg">{net.error || 'That team name is taken - please pick another.'}</p>
      {/if}
      <div class="row">
        <!-- svelte-ignore a11y_autofocus -->
        <input class="grow" bind:value={name} placeholder="Your team name" maxlength="24" autofocus />
        <button class="primary" type="submit" disabled={!name.trim()}>Join</button>
      </div>
    </form>
  </div>
{:else if net.data}
  <Team />
{:else}
  <div class="center dim">Connecting …</div>
{/if}

{#if joined && !net.rejected && !net.connected}
  <div class="banner warn">Connection lost - reconnecting …</div>
{/if}
