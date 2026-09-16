<script>
  // Shell (#659, navigation #2419, #2667): pairing gate, the player (its side panel holds the navigation) and the
  // settings panel over it. One MIDI socket for the whole app; screens
  // subscribe to its frames and messages.
  import { onDestroy, untrack } from "svelte";
  import { ensurePaired, openMidiSocket } from "./lib/pair.js";
  import { parseRoute, routePath } from "./lib/routes.js";
  import Player from "./Player.svelte";
  import Settings from "./Settings.svelte";
  import { metroLive, attachMetronome, metronomeLink, toggleMetronome } from "./lib/metronome.svelte.js";
  import { prefs } from "./lib/prefs.svelte.js";

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
  // The metronome belongs to the piano view (the score, or playing freely): the game view has its own beat.
  $effect(() => {
    if (prefs.view !== "game") return;
    untrack(() => {
      if (metroLive.running) toggleMetronome();
      if (panel === "metronome") navigate({ panel: null });
    });
  });

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

{#if pairing !== "paired"}
  <header><span class="title">pisynth</span></header>
{/if}

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
  <!-- no top bar (#2667): the player's side panel holds the navigation, settings open from there -->
  <Player {onFrame} {onMessage} {send} mode={prefs.view === "piano" ? "play" : mode} onMode={m => navigate({ mode: m, panel: null })}
          onPanel={p => navigate({ panel: p })} {link} />
  {#if panel}
    <Settings {panel} onPanel={p => navigate({ panel: p })} onClose={() => navigate({ panel: null })} {onFrame} {onMessage} {send} />
  {/if}
{/if}
