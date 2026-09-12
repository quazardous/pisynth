<script>
  // Shell (#659): pairing gate, header, and the two views (/ live, /latency). One MIDI socket
  // for the whole app; views subscribe to its frames.
  import { onDestroy } from "svelte";
  import { ensurePaired, openMidiSocket } from "./lib/pair.js";
  import Live from "./Live.svelte";
  import Latency from "./Latency.svelte";
  import Demo from "./Demo.svelte";
  import Sound from "./Sound.svelte";

  const ROUTES = ["/", "/sound", "/latency", "/demo"];
  const route = () => (ROUTES.includes(location.pathname) ? location.pathname : "/");
  let path = $state(route());
  let pairing = $state("checking");               // checking | paired | unpaired | expired | offline
  let link = $state("…");
  const listeners = new Set();
  let socket;

  function go(to, e) {
    e?.preventDefault();
    history.pushState(null, "", to);
    path = to;
  }
  addEventListener("popstate", () => (path = route()));

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
    <nav>
      <a href="/" class:active={path === "/"} onclick={e => go("/", e)}>Live</a>
      <a href="/sound" class:active={path === "/sound"} onclick={e => go("/sound", e)}>Sound</a>
      <a href="/demo" class:active={path === "/demo"} onclick={e => go("/demo", e)}>Demo</a>
      <a href="/latency" class:active={path === "/latency"} onclick={e => go("/latency", e)}>Latency</a>
    </nav>
    <span class="status" class:on={link === "live"}>{link}</span>
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
{:else if path === "/sound"}
  <Sound {onMessage} {send} />
{:else if path === "/demo"}
  <Demo {onFrame} {onMessage} {send} />
{:else if path === "/latency"}
  <Latency {onFrame} />
{:else}
  <Live {onFrame} />
{/if}
