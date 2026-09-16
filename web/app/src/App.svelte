<script>
  // Shell (#659, navigation #2419): pairing gate, top bar with the cog, the player (one screen,
  // "I play / Listen") and the settings panel over it. One MIDI socket for the whole app; screens
  // subscribe to its frames and messages.
  import { onDestroy } from "svelte";
  import { ensurePaired, openMidiSocket } from "./lib/pair.js";
  import { parseRoute, routePath } from "./lib/routes.js";
  import Player from "./Player.svelte";
  import Settings from "./Settings.svelte";
  import { musicians, selectMusician } from "./lib/musician.svelte.js";
  import { metroLive, attachMetronome, metronomeLink } from "./lib/metronome.svelte.js";

  const initial = parseRoute(location.pathname);
  let mode = $state(initial.mode ?? "play");
  let panel = $state(initial.panel);
  let pairing = $state("checking");               // checking | paired | unpaired | expired | offline
  let link = $state("…");
  const listeners = new Set();
  let socket;

  function navigate(next) {
    mode = next.mode ?? mode;
    panel = next.panel;
    const path = routePath({ mode, panel });
    if (path !== location.pathname) history.pushState(null, "", path);
  }
  addEventListener("popstate", () => {
    const r = parseRoute(location.pathname);
    panel = r.panel;
    if (r.mode) mode = r.mode;
  });

  const onFrame = fn => { listeners.add(fn); return () => listeners.delete(fn); };
  const msgListeners = new Set();
  const onMessage = fn => { msgListeners.add(fn); return () => msgListeners.delete(fn); };
  const send = obj => socket?.send(obj) ?? false;
  attachMetronome({ onMessage, send });           // the companion manages pisynth's metronome (#2658)

  async function connect() {
    socket?.close();
    socket = null;
    const state = await ensurePaired();
    pairing = state;
    if (state === "offline") { setTimeout(connect, 3000); return; }   // pisynth restarting / unreachable: retry
    if (state !== "paired") return;
    socket = openMidiSocket({
      onFrame: buf => listeners.forEach(fn => fn(buf)),
      onMessage: msg => msgListeners.forEach(fn => fn(msg)),
      onState: st => {
        if (st === "unpaired") pairing = "unpaired";
        link = st === "live" ? "live" : "reconnecting…";
        metronomeLink(st === "live");
        listeners.forEach(fn => fn(null));        // null = link dropped: views reset held notes
      },
    });
  }
  connect();
  // A new pairing link opened in an already-open tab only changes the #fragment: no reload.
  addEventListener("hashchange", () => { if (/[#&]k=/.test(location.hash)) connect(); });
  onDestroy(() => socket?.close());
</script>

<header>
  {#if pairing === "paired"}
    <label class="who" style:--mc={musicians.list.find(m => m.id === musicians.current)?.color}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0 2c-4 0-8 2-8 5v1h16v-1c0-3-4-5-8-5z" /></svg>
      <select value={musicians.current} onchange={e => selectMusician(e.target.value)} aria-label="who is playing">
        {#each musicians.list as m (m.id)}<option value={m.id}>{m.name}</option>{/each}
      </select>
    </label>
  {:else}
    <span class="title">pisynth</span>
  {/if}
  {#if pairing === "paired"}
    <span class="status" class:on={link === "live"}>{link}</span>
    <button class="metrobtn" class:running={metroLive.running} class:beat={metroLive.beat > 0} class:one={metroLive.beat === 1}
            onclick={() => navigate({ panel: panel === "metronome" ? null : "metronome" })} aria-label="metronome">
      {#key metroLive.beat}<svg viewBox="0 0 24 24"><path d="M9.2 2h5.6l4.4 18.5A1.2 1.2 0 0 1 18 22H6a1.2 1.2 0 0 1-1.2-1.5zM7.4 16h9.2l-.9-3.8-3.2 3.2-1.3-1.3 3.9-3.9L13.2 4h-2.4z" /></svg>{/key}
    </button>
    <button class="cog" onclick={() => navigate({ panel: panel ? null : "sound" })} aria-label="settings">
      <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94s-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96a7 7 0 0 0-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84a.47.47 0 0 0-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.48.48 0 0 0-.59.22L2.74 8.87a.47.47 0 0 0 .12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.47.47 0 0 0-.12-.61zM12 15.6a3.6 3.6 0 1 1 0-7.2 3.6 3.6 0 0 1 0 7.2z" /></svg>
    </button>
  {/if}
</header>

{#if pairing === "checking"}
  <section class="card"><p class="muted">Connecting to pisynth…</p></section>
{:else if pairing !== "paired"}
  <section class="card">
    <h1>Pair this phone</h1>
    {#if pairing === "expired"}
      <p>That pairing code has expired. Tap the QR icon next to the metronome on the pisynth screen and scan again.</p>
    {:else if pairing === "offline"}
      <p>Can't reach pisynth — retrying… Is this phone on the same Wi-Fi?</p>
    {:else}
      <p>On the pisynth screen, tap the <b>QR icon</b> next to the metronome, then scan the code with this phone.</p>
      <p class="muted">Only one browser can be paired: if another one was paired after this one, this one was disconnected.</p>
    {/if}
  </section>
{:else}
  <Player {onFrame} {onMessage} {send} {mode} onMode={m => navigate({ mode: m, panel: null })} />
  {#if panel}
    <Settings {panel} onPanel={p => navigate({ panel: p })} onClose={() => navigate({ panel: null })} {onFrame} {onMessage} {send} />
  {/if}
{/if}

<style>
  /* the musician playing, in place of the title: a dropdown to choose (names are edited under the cog → Musicians) */
  .who { position: relative; display: inline-flex; align-items: center; height: 38px; min-width: 0; max-width: 70%; border-radius: 19px;
         border: 2px solid var(--mc, #c38bff); background: linear-gradient(rgba(18,18,24,.62), rgba(18,18,24,.62)), var(--mc, #c38bff); }
  .who svg { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); width: 20px; height: 20px; fill: var(--mc, #c38bff); pointer-events: none; }
  .who::after { content: ""; position: absolute; right: 12px; top: 50%; width: 7px; height: 7px; pointer-events: none;
                border-right: 2px solid var(--mc, #c38bff); border-bottom: 2px solid var(--mc, #c38bff); transform: translateY(-70%) rotate(45deg); }
  .who select { -webkit-appearance: none; appearance: none; display: block; height: 100%; min-width: 10.5em; max-width: 100%; margin: 0;
                padding: 0 32px 0 34px; border: 0; border-radius: 19px; background: transparent; color: #fff; font: inherit; font-weight: 700;
                line-height: 34px; text-overflow: ellipsis; white-space: nowrap; overflow: hidden; cursor: pointer; }
  .who option { color: #121218; background: #fff; }
  .metrobtn { margin: 0 0 0 4px; padding: 6px; background: none; display: grid; place-items: center; border-radius: 50%; }
  .metrobtn svg { width: 24px; height: 24px; fill: var(--muted); }
  .metrobtn.running svg { fill: var(--accent); }
  .metrobtn.running.beat svg { animation: metro-pulse .18s ease-out; }
  .metrobtn.running.one svg { fill: var(--yellow); }
  @keyframes metro-pulse { from { transform: scale(1.25); } to { transform: scale(1); } }
  .cog { margin: 0 0 0 4px; padding: 6px; background: none; display: grid; place-items: center; border-radius: 50%; }
  .cog svg { width: 24px; height: 24px; fill: var(--muted); }
  .cog:active svg { fill: var(--fg); }
</style>
