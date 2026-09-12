<script>
  // Shell (#659, navigation #2419): pairing gate, top bar with the cog, the player (one screen,
  // "I play / Listen") and the settings panel over it. One MIDI socket for the whole app; screens
  // subscribe to its frames and messages.
  import { onDestroy } from "svelte";
  import { ensurePaired, openMidiSocket } from "./lib/pair.js";
  import { parseRoute, routePath } from "./lib/routes.js";
  import Player from "./Player.svelte";
  import Settings from "./Settings.svelte";

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
  <span class="title">pisynth</span>
  {#if pairing === "paired"}
    <span class="status" class:on={link === "live"}>{link}</span>
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
  .cog { margin: 0 0 0 4px; padding: 6px; background: none; display: grid; place-items: center; border-radius: 50%; }
  .cog svg { width: 24px; height: 24px; fill: var(--muted); }
  .cog:active svg { fill: var(--fg); }
</style>
