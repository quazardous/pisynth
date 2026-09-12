<script>
  // Demo mode (#2416): play a song THROUGH pisynth — the phone streams timed notes, the synth
  // sounds them. Demo notes light yellow on the keyboard; what you play lights blue.
  import { decodeFrame, NoteState } from "./lib/midi.js";
  import { parseMidi, sampleSong } from "./lib/midifile.js";
  import { DemoSender } from "./lib/demo.js";
  import { detectChord, noteName } from "./lib/theory.js";
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
  let options = $state(false);                    // song + tempo sheet, folded by default (compact player)
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

  function seek(e) {
    const to = Number(e.target.value);
    if (playing) { stop(); position = to; start(); } else position = to;
  }

  const sounding = $derived([...new Set([...demoOn, ...liveOn])].sort((a, b) => a - b));
  const chord = $derived(detectChord(sounding));

  function retempo() { if (playing) { const p = sender.position(); stop(); position = p; start(); } }
  const fmt = ms => { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
</script>

<main>
  <div class="stage">
    <div class="chord">{chord || " "}</div>
    <div class="notes">{sounding.map(noteName).join(" ") || " "}</div>
    {#if error}<p class="error">{error}</p>{:else if status}<p class="muted">{status}</p>{/if}
  </div>

  {#if options}
    <section class="sheet">
      <label class="file">MIDI file <input type="file" accept=".mid,.midi,audio/midi" onchange={loadFile}></label>
      <button class="link" onclick={() => { stop(); song = sampleSong(); position = 0; }}>use the sample</button>
      <label>Tempo {tempo}% <input type="range" min="50" max="150" step="5" bind:value={tempo} onchange={retempo}></label>
      <p class="muted">Plays the song through the synth. Your own playing lights blue, the demo yellow.</p>
    </section>
  {/if}

  <div class="player">
    <button class="play" onclick={() => (playing ? stop() : start())} aria-label={playing ? "Stop" : "Play"}>
      {#if playing}
        <svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5" /></svg>
      {:else}
        <svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z" /></svg>
      {/if}
    </button>
    <div class="meta">
      <div class="name">{song.name || "untitled"}</div>
      <input class="seek" type="range" min="0" max={song.durationMs || 1} step="100"
             value={Math.min(position, song.durationMs)} onchange={seek} aria-label="position">
      <div class="time">{fmt(position)} / {fmt(song.durationMs)}{tempo !== 100 ? ` · ${tempo}%` : ""}</div>
    </div>
    <button class="more" class:open={options} onclick={() => (options = !options)} aria-label="song and tempo">
      <svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" /></svg>
    </button>
  </div>
  <Keyboard on={liveOn} demo={demoOn} />
</main>

<style>
  main { flex: 1; display: flex; flex-direction: column; min-height: 0; }
  .stage { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; padding: 12px; min-height: 0; }
  .chord { font-size: clamp(2.2rem, 12vw, 4.5rem); font-weight: 800; color: var(--yellow); }
  .notes { font-size: clamp(.9rem, 4.5vw, 1.4rem); color: var(--muted); letter-spacing: 1px; }
  .error { color: #ff7a7a; }
  .sheet { margin: 0 12px 8px; padding: 12px 14px; background: var(--bar); border-radius: 12px; }
  .sheet label { display: block; margin-top: 8px; }
  .sheet label:first-child { margin-top: 0; }
  .sheet input[type="range"] { width: 100%; }
  .sheet p { margin-top: 8px; }
  .file input { display: block; margin-top: 6px; color: var(--muted); max-width: 100%; }
  .link { background: none; color: var(--accent); padding: 4px 0; margin-top: 4px; font-weight: 400; }
  .player { display: flex; align-items: center; gap: 10px; padding: 6px 12px; background: var(--bar); }
  .player button { margin: 0; padding: 0; display: grid; place-items: center; flex: 0 0 auto; }
  .play { width: 44px; height: 44px; border-radius: 50%; }
  .play svg { width: 22px; height: 22px; fill: #fff; }
  .more { width: 36px; height: 36px; border-radius: 50%; background: none; }
  .more svg { width: 20px; height: 20px; fill: var(--muted); }
  .more.open svg { fill: var(--accent); }
  .meta { flex: 1; min-width: 0; }
  .name { font-size: .85rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .seek { width: 100%; height: 18px; margin: 0; accent-color: var(--accent); display: block; }
  .time { font-size: .75rem; color: var(--muted); font-variant-numeric: tabular-nums; }
</style>
