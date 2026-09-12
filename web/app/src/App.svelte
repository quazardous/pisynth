<script>
  // Shell (#659): pairing gate, header, and the two views (/ live, /latency). One MIDI socket
  // for the whole app; views subscribe to its frames.
  import { onDestroy } from "svelte";
  import { ensurePaired, openMidiSocket } from "./lib/pair.js";
  import Live from "./Live.svelte";
  import Latency from "./Latency.svelte";

  let path = $state(location.pathname === "/latency" ? "/latency" : "/");
  let pairing = $state("checking");               // checking | paired | unpaired | expired | offline
  let link = $state("…");
  const listeners = new Set();
  let socket;

  function go(to, e) {
    e?.preventDefault();
    history.pushState(null, "", to);
    path = to;
  }
  addEventListener("popstate", () => (path = location.pathname === "/latency" ? "/latency" : "/"));

  const onFrame = fn => { listeners.add(fn); return () => listeners.delete(fn); };

  ensurePaired().then(state => {
    pairing = state;
    if (state !== "paired") return;
    socket = openMidiSocket({
      onFrame: buf => listeners.forEach(fn => fn(buf)),
      onState: st => {
        if (st === "unpaired") pairing = "unpaired";
        link = st === "live" ? "live" : "reconnecting…";
        listeners.forEach(fn => fn(null));        // null = link dropped: views reset held notes
      },
    });
  });
  onDestroy(() => socket?.close());
</script>

<header>
  <span class="title">pisynth</span>
  {#if pairing === "paired"}
    <nav>
      <a href="/" class:active={path === "/"} onclick={e => go("/", e)}>Live</a>
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
      <p>Can't reach pisynth. Is this phone on the same Wi-Fi?</p>
    {:else}
      <p>On the pisynth screen, tap the <b>QR icon</b> next to the metronome, then scan the code with this phone.</p>
    {/if}
  </section>
{:else if path === "/latency"}
  <Latency {onFrame} />
{:else}
  <Live {onFrame} />
{/if}
