<script>
  // Demo mode (#2416): play a song THROUGH pisynth — the phone streams timed notes, the synth
  // sounds them. Demo notes light yellow on the keyboard; what you play lights blue.
  import { decodeFrame, NoteState } from "./lib/midi.js";
  import { parseMidi, sampleSong } from "./lib/midifile.js";
  import { DemoSender } from "./lib/demo.js";
  import Keyboard from "./Keyboard.svelte";

  let { onFrame, onMessage, send } = $props();
  let song = $state(sampleSong());
  let error = $state("");
  let tempo = $state(100);                        // %
  let playing = $state(false);
  let status = $state("");
  let position = $state(0);
  let demoOn = $state(new Set());
  let liveOn = $state(new Set());
  let sender = null, timer = 0, raf = 0, startClock = 0, leadMs = 150;
  const held = new NoteState();

  $effect(() => {
    const offF = onFrame(buf => {                   // your own playing, in blue
      if (buf === null) held.clear(); else if (!held.apply(decodeFrame(buf))) return;
      liveOn = new Set(held.sounding());
    });
    const offM = onMessage(msg => {
      if (msg.t !== "demo") return;
      if (msg.state === "playing") { leadMs = msg.lead_ms ?? 150; status = "playing on pisynth"; }
      if (msg.state === "error") { status = "pisynth: " + msg.error; stop(false); }
      if (msg.state === "stopped" && msg.by === "pisynth") { stop(false); status = "stopped on pisynth"; }
    });
    return () => { offF(); offM(); stop(); };
  });

  async function loadFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    stop();
    try { song = { ...parseMidi(await f.arrayBuffer()), name: f.name }; error = ""; position = 0; }
    catch (err) { error = err.message; }
  }

  function start() {
    if (!song.events.length) return;
    const from = position >= song.durationMs ? 0 : position;
    sender = new DemoSender({ events: song.events, send });
    sender.start(from, tempo / 100);
    startClock = performance.now();
    playing = true; status = "starting…";
    timer = setInterval(() => {
      sender.tick();
      paint();                                       // also here: rAF pauses when the page isn't painted
      if (sender.done && sender.position() > song.durationMs + 500) stop(false);
    }, 150);
    const paint = () => {                            // light the demo notes when the Pi plays them
      const t = performance.now() - startClock - leadMs;
      const on = new Set(), sus = [];
      for (const ev of song.events) {
        const at = sender.offset(ev);
        if (at < 0) continue;
        if (at > t) break;
        const kind = ev.status & 0xf0;
        if (kind === 0x90 && ev.d2 > 0) on.add(ev.d1); else if (kind === 0x80 || kind === 0x90) on.delete(ev.d1);
      }
      demoOn = on;
      position = sender.position();
    };
    const animate = () => { if (!sender) return; paint(); raf = requestAnimationFrame(animate); };
    raf = requestAnimationFrame(animate);
  }

  function stop(tell = true) {
    clearInterval(timer); cancelAnimationFrame(raf);
    if (sender) position = sender.position();        // where it stopped, before the sender forgets
    if (sender && tell) sender.stop(); else if (sender) sender.playing = false;
    sender = null; playing = false; demoOn = new Set();
    if (tell) status = "";
  }

  function retempo() { if (playing) { const p = sender.position(); stop(); position = p; start(); } }
  const fmt = ms => { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
</script>

<main>
  <section class="card">
    <h1>Demo on pisynth</h1>
    <p class="muted">Plays a song through the synth, so you hear it on the instrument. Your own playing lights blue, the demo yellow.</p>
    <label class="file">MIDI file <input type="file" accept=".mid,.midi,audio/midi" onchange={loadFile}></label>
    <button class="link" onclick={() => { stop(); song = sampleSong(); position = 0; }}>use the sample</button>
    {#if error}<p class="error">{error}</p>{/if}
    <p class="song"><b>{song.name || "untitled"}</b> · {fmt(song.durationMs)} · {song.events.length} events</p>
    <label>Tempo {tempo}% <input type="range" min="50" max="150" step="5" bind:value={tempo} onchange={retempo}></label>
    <div class="row">
      {#if playing}<button onclick={() => stop()}>Stop</button>{:else}<button onclick={start}>{position > 0 && position < song.durationMs ? "Resume" : "Play"}</button>{/if}
      <span class="muted">{fmt(position)} / {fmt(song.durationMs)} {status && `· ${status}`}</span>
    </div>
    <progress max={song.durationMs || 1} value={Math.min(position, song.durationMs)}></progress>
  </section>
  <Keyboard on={liveOn} demo={demoOn} />
</main>

<style>
  main { flex: 1; display: flex; flex-direction: column; min-height: 0; justify-content: space-between; }
  label { display: block; margin-top: 12px; }
  input[type="range"] { width: 100%; }
  .file input { display: block; margin-top: 6px; color: var(--muted); }
  .link { background: none; color: var(--accent); padding: 4px 0; margin-top: 6px; font-weight: 400; }
  .song { margin-top: 12px; }
  .row { display: flex; align-items: center; gap: 14px; }
  progress { width: 100%; margin-top: 12px; }
  .error { color: #ff7a7a; margin-top: 8px; }
</style>
