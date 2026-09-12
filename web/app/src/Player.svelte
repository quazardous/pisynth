<script>
  // The companion's main screen (#2419): one player, two modes, same design.
  //  - "I play" (#2418): notes fall onto the keyboard, you play them, the phone judges each press
  //    on the Pi's own timestamps (lib/clock.js + lib/judge.js). pisynth only plays a count-in.
  //  - "Listen" (#2416): pisynth plays the song (lib/demo.js streams it), the same notes fall and
  //    light up as the synth sounds them.
  // Tempo, A–B loop and position are shared, so you can listen to a passage then play it.
  // With no song loaded the screen is the live keyboard + chord name (the old Live tab, #659).
  import { onDestroy, untrack } from "svelte";
  import { decodeFrame, NoteState } from "./lib/midi.js";
  import { sampleSong } from "./lib/midifile.js";
  import { songNotes, noteRange, noteTracks, visibleNotes, longestNote, timeToY } from "./lib/highway.js";
  import { planView, FollowView, keyRect, toPct } from "./lib/viewport.js";
  import { Judge } from "./lib/judge.js";
  import { ClockSync } from "./lib/clock.js";
  import { DemoSender } from "./lib/demo.js";
  import { detectChord, noteName } from "./lib/theory.js";
  import { enterPlayMode, exitPlayMode, releaseAwake } from "./lib/screen.js";
  import Keyboard from "./Keyboard.svelte";
  import Library from "./Library.svelte";

  let { onFrame, onMessage, send, mode = "play", onMode = () => {} } = $props();

  const AHEAD_MS = 2600;           // real ms of music visible above the line
  const PAST_MS = 300;             // a note stays drawn this long after it ends
  const FOLLOW_AHEAD_MS = 2000;    // the sliding window looks this far ahead
  const COUNT_IN = 4;
  const TRACK_COLORS = ["#5aa0ff", "#4fd18b", "#c38bff", "#ff9f5a"];
  const EMPTY = { events: [], durationMs: 0, name: "" };

  let song = $state.raw(null);
  let error = $state("");
  let status = $state("");
  let tempo = $state(100);
  let playing = $state(false);
  let position = $state(0);        // song ms shown on the bar
  let loop = $state(null);         // {a, b} song ms
  let options = $state(false);
  let finished = $state(false);
  let countIn = $state(0);
  let stats = $state({ score: 0, streak: 0, accuracy: 0 });
  let flash = $state(null);        // {kind, delta, id}
  let liveOn = $state(new Set());
  let guide = $state(new Set());
  let view = $state({ x0: 0, span: 15 });
  let stageW = $state(0), stageH = $state(0);
  let canvas = $state(null);

  const current = $derived(song ?? EMPTY);
  const notes = $derived(songNotes(current.events, current.durationMs).map((n, i) => ({ ...n, i })));
  const maxLen = $derived(longestNote(notes));
  const range = $derived(noteRange(notes));
  const hands = $derived(noteTracks(notes));
  const plan = $derived(song && stageW ? planView(range.low, range.high, stageW) : null);
  const sounding = $derived([...liveOn].sort((a, b) => a - b));

  let judge = $state.raw(new Judge([]));             // (raw: its counters are read, not tracked)
  const clock = new ClockSync();
  const held = new NoteState();
  let follow = null, effects = [], origin = 0, clockStart = 0, from = 0, clicked = false;
  let sender = null, leadMs = 150;
  let raf = 0, timer = 0, lastPaint = 0, flashId = 0;

  $effect(() => {                                   // a new song: fresh judge, back to the start
    const n = notes;
    untrack(() => { judge = new Judge(n, { tempo: tempo / 100 }); position = 0; loop = null; finished = false; });
  });
  $effect(() => {                                   // song or screen width changed: re-plan the view
    const p = plan, first = notes.slice(0, 8).map(n => n.note);
    if (!p) return;
    untrack(() => {
      follow = p.mode === "follow" ? new FollowView(p) : null;
      if (follow) { follow.aim([], first); follow.jump(follow.target); }
      view = follow ? { x0: follow.x0, span: follow.span } : { x0: p.x0, span: p.span };
      paint();
    });
  });
  $effect(() => { mode; untrack(() => { if (playing) stop(); finished = false; flash = null; paint(); }); });   // switching keeps the position

  const tf = () => tempo / 100;
  const songPos = now => origin + (now - clockStart) * tf();
  const beatMs = () => 60000 / (current.bpm || 100);         // song ms per beat

  $effect(() => {
    const offF = onFrame(buf => {
      if (buf === null) { held.clear(); liveOn = new Set(); return; }
      const now = performance.now();
      const ev = decodeFrame(buf);
      if (!ev) return;
      clock.observe(ev.t, now);
      if (ev.type === "on" && playing && mode === "play") {
        const at = clock.toLocal(ev.t) ?? now;
        const t = songPos(at);
        if (t >= from - 400) show(judge.press(ev.note, t), now);
      }
      if (held.apply(ev)) liveOn = new Set(held.sounding());
    });
    const offM = onMessage(msg => {
      if (msg.t !== "demo") return;
      if (msg.state === "error") { error = "pisynth: " + msg.error; stop(false); }
      if (msg.state === "playing" && msg.lead_ms) leadMs = msg.lead_ms;
      if (msg.state === "stopped" && msg.by === "pisynth" && playing && mode === "listen") { stop(false); status = "stopped on pisynth"; }
    });
    return () => { offF(); offM(); };
  });

  function show(r, now) {
    effects.push({ ...r, at: now });
    flash = { kind: r.kind, delta: r.delta, id: ++flashId };
    stats = { score: judge.score, streak: judge.streak, accuracy: judge.accuracy() };
  }

  function load(s) {
    stop();
    song = s; error = ""; status = ""; options = false;
  }

  function start(at = null) {
    if (!notes.length) return;
    from = at ?? loop?.a ?? (position >= current.durationMs ? 0 : position);
    const now = performance.now();
    origin = from;
    effects = []; finished = false; flash = null; error = ""; status = "";
    if (mode === "listen") {
      sender = new DemoSender({ events: current.events, send });
      sender.start(from, tf());
      clicked = true;
      clockStart = now + leadMs;                              // the Pi anchors the song this far ahead
    } else {
      const beatReal = beatMs() / tf();
      clockStart = now + leadMs + COUNT_IN * beatReal;        // the song reaches `from` after the count-in
      judge.setTempo(tf());
      judge.reset(from);
      stats = { score: 0, streak: 0, accuracy: 0 };
      const ev = [];                                          // wood-block count-in, played by pisynth
      for (let k = 0; k < COUNT_IN; k++) ev.push([k * beatReal, 0x99, k ? 76 : 77, k ? 90 : 120], [k * beatReal + 60, 0x89, k ? 76 : 77, 0]);
      clicked = send({ t: "play", reset: true, ev }) !== false;
    }
    playing = true;
    enterPlayMode();
    timer = setInterval(() => {
      sender?.tick();                                         // listen: next look-ahead batch
      if (performance.now() - lastPaint > 120) paint();       // rAF pauses when the page isn't painted
    }, 120);
    const loopFn = () => { if (!playing) return; paint(); raf = requestAnimationFrame(loopFn); };
    raf = requestAnimationFrame(loopFn);
  }

  function stop(tell = true) {
    if (!playing) return;
    clearInterval(timer); cancelAnimationFrame(raf);
    position = Math.max(from, Math.min(songPos(performance.now()), current.durationMs));
    if (sender) { if (tell) sender.stop(); else sender.playing = false; sender = null; }
    else if (tell && clicked) send({ t: "stop" });
    playing = false; countIn = 0; guide = new Set();
    releaseAwake();
    paint();
  }

  function finish() {
    const judged = mode === "play";
    stop();
    position = judged ? current.durationMs : 0;
    finished = judged;
  }

  function seek(e) {
    const to = Number(e.target.value);
    if (playing) { stop(); start(to); } else { position = to; paint(); }
  }

  function retempo() { if (playing) { const p = songPos(performance.now()); stop(); start(Math.max(0, p)); } }

  const setA = () => (loop = { a: Math.min(position, loop?.b ?? Infinity), b: loop?.b ?? current.durationMs });
  const setB = () => (loop = { a: loop?.a ?? 0, b: Math.max(position, (loop?.a ?? 0) + 500) });

  let lastT = null;
  function paint() {
    lastPaint = performance.now();
    const now = lastPaint;
    const t = playing ? songPos(now) : position;
    const dt = lastT === null ? 0 : now - lastT;
    lastT = now;
    if (!song) return;

    if (playing) {
      if (mode === "play") {
        const missed = judge.advance(t);
        for (const i of missed) effects.push({ kind: "miss", note: notes[i].note, index: i, at: now });
        if (missed.length) stats = { score: judge.score, streak: judge.streak, accuracy: judge.accuracy() };
        countIn = t < from ? Math.min(COUNT_IN, Math.ceil((from - t) / beatMs())) : 0;
      }
      if (loop && t >= loop.b) { stop(false); start(loop.a); return; }
      if (t > current.durationMs + 800) { finish(); return; }
      if (Math.abs(Math.max(from, t) - position) > 100) position = Math.max(from, t);    // (count-in: stays at the start)
      const lit = new Set(), ahead = mode === "play" ? 60 * tf() : 0;   // play: keys due now · listen: keys sounding
      for (const n of visibleNotes(notes, t, ahead, 0, maxLen)) if (n.start <= t + ahead && n.end >= t) lit.add(n.note);
      if (lit.size !== guide.size || [...lit].some(n => !guide.has(n))) guide = lit;
    }

    if (follow) {
      const soon = visibleNotes(notes, t, FOLLOW_AHEAD_MS * tf(), 0, maxLen);
      follow.aim(soon.filter(n => n.start <= t).map(n => n.note), soon.filter(n => n.start > t).map(n => n.note));
      const v = follow.step(dt);
      if (Math.abs(v.x0 - view.x0) > 0.002 || v.span !== view.span) view = { x0: v.x0, span: v.span };
    }
    draw(t, now);
  }

  function draw(t, now) {
    if (!canvas || !stageW || !stageH) return;
    const dpr = globalThis.devicePixelRatio || 1;
    const W = Math.round(stageW * dpr), H = Math.round(stageH * dpr);
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    const ctx = canvas.getContext("2d");
    const v = follow ? { x0: follow.x0, span: follow.span } : view;
    const hitY = H - 3 * dpr, pxPerMs = hitY / (AHEAD_MS * tf());
    const xOf = r => { const p = toPct(r, v); return [(p.left / 100) * W, (p.width / 100) * W]; };
    const judged = mode === "play";

    ctx.clearRect(0, 0, W, H);
    for (let n = 21; n <= 108; n++) {                          // lanes: black keys darker, a line at each C
      const r = keyRect(n);
      if (r.x + r.w < v.x0 || r.x > v.x0 + v.span) continue;
      const [x, w] = xOf(r);
      if (r.black) { ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.fillRect(x, 0, w, hitY); }
      else if (n % 12 === 0) { ctx.fillStyle = "rgba(255,255,255,.07)"; ctx.fillRect(x, 0, 1 * dpr, hitY); }
    }

    const res = judge.result;
    for (const n of visibleNotes(notes, t, AHEAD_MS * tf(), PAST_MS * tf(), maxLen)) {
      const r = keyRect(n.note);
      let [x, w] = xOf(r);
      if (x + w < 0 || x > W) continue;
      x += 1.5 * dpr; w = Math.max(2 * dpr, w - 3 * dpr);
      const yTop = Math.max(-10, timeToY(n.end, t, hitY, pxPerMs)), yBot = timeToY(n.start, t, hitY, pxPerMs);
      const h = Math.max(6 * dpr, yBot - yTop);
      let color = TRACK_COLORS[Math.max(0, hands.indexOf(n.track)) % TRACK_COLORS.length], alpha = r.black ? 0.85 : 1;
      if (judged) {
        const state = res[n.i];
        if (state === "perfect" || state === "good") color = "#ffd23f";
        else if (state === "early" || state === "late") color = "#ff9f5a";
        else if (state === "miss") color = "#4a4a58";
        if (state === "skip") alpha = 0.25;
      } else if (playing && n.start <= t) {
        color = "#ffd23f";                                      // listen: lit while pisynth plays it
        if (n.end < t) alpha = 0.35;
      }
      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, yBot - h, w, h, 4 * dpr) : ctx.rect(x, yBot - h, w, h);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    effects = effects.filter(e => now - e.at < 450);            // hit / miss glow on the line
    for (const e of effects) {
      if (e.kind === "wrong") continue;
      const [x, w] = xOf(keyRect(e.note));
      const a = 1 - (now - e.at) / 450;
      ctx.fillStyle = e.kind === "miss" ? `rgba(255,90,90,${a * 0.5})` : `rgba(255,210,63,${a * 0.8})`;
      ctx.fillRect(x - 4 * dpr, hitY - 26 * dpr * a, w + 8 * dpr, 26 * dpr * a);
    }

    ctx.fillStyle = "#ffd23f";                                  // the hit line
    ctx.fillRect(0, hitY, W, 3 * dpr);

    if (follow) {                                               // arrows: notes coming outside the window
      for (const n of visibleNotes(notes, t, FOLLOW_AHEAD_MS * tf(), 0, maxLen)) {
        const r = keyRect(n.note), left = r.x + r.w <= v.x0, right = r.x >= v.x0 + v.span;
        if (!left && !right) continue;
        const y = Math.max(12 * dpr, timeToY(n.start, t, hitY, pxPerMs));
        const x = left ? 4 * dpr : W - 4 * dpr, s = (left ? 1 : -1) * 10 * dpr;
        ctx.fillStyle = "rgba(255,255,255,.75)";
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + s, y - 7 * dpr); ctx.lineTo(x + s, y + 7 * dpr); ctx.fill();
      }
    }
  }

  $effect(() => { stageW; stageH; view; song; untrack(() => { if (!playing) paint(); }); });   // redraw when idle and resized
  onDestroy(() => { stop(); exitPlayMode(); });

  const fmt = ms => { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const pct = ms => `${(Math.min(ms, current.durationMs) / (current.durationMs || 1)) * 100}%`;
  const LABEL = { perfect: "perfect", good: "good", early: "early", late: "late", wrong: "wrong note", miss: "miss" };
</script>

<main>
  <div class="hud">
    <div class="toggle" role="group" aria-label="mode">
      <button class:on={mode === "play"} onclick={() => onMode("play")}>I play</button>
      <button class:on={mode === "listen"} onclick={() => onMode("listen")}>Listen</button>
    </div>
    {#if song && mode === "play"}
      <span class="score">{stats.score}</span>
      {#if stats.streak > 1}<span class="streak">×{stats.streak}</span>{/if}
      <span class="acc">{stats.accuracy}%</span>
    {/if}
    <span class="song">{song ? song.name || "untitled" : ""}</span>
  </div>

  {#if song}
    <div class="stage" bind:clientWidth={stageW} bind:clientHeight={stageH}>
      <canvas bind:this={canvas}></canvas>
      {#if countIn}<div class="count">{countIn}</div>{/if}
      {#key flash?.id}
        {#if flash && playing}
          <div class="flash {flash.kind}">{LABEL[flash.kind]}{#if flash.delta !== undefined && flash.kind !== "perfect"} <small>{flash.delta > 0 ? "+" : ""}{Math.round(flash.delta)} ms</small>{/if}</div>
        {/if}
      {/key}
      {#if finished}
        <section class="results">
          <h2>{stats.accuracy}%</h2>
          <p><b>{judge.score}</b> points · best streak {judge.bestStreak}</p>
          <p class="muted">perfect {judge.counts.perfect} · good {judge.counts.good} · early {judge.counts.early} · late {judge.counts.late} · missed {judge.counts.miss} · wrong {judge.counts.wrong}</p>
          <button onclick={() => { finished = false; start(loop?.a ?? 0); }}>Play again</button>
        </section>
      {/if}
      {#if error}<p class="error">{error}</p>{:else if status}<p class="status-msg">{status}</p>{/if}
    </div>
  {:else}
    <div class="live">
      <div class="chord">{detectChord(sounding) || " "}</div>
      <div class="notes">{sounding.map(noteName).join(" ") || " "}</div>
      <button class="choose" onclick={() => (options = true)}>Choose a song</button>
    </div>
  {/if}

  {#if options}
    <section class="sheet">
      <Library current={song?.path} onPick={load} />
      <button class="link" onclick={() => load(sampleSong())}>use the built-in sample</button>
      {#if song}
        <label>Tempo {tempo}% <input type="range" min="50" max="150" step="5" bind:value={tempo} onchange={retempo}></label>
        <div class="loop">
          <span>Loop</span>
          <button class="small" onclick={setA}>A = {fmt(loop?.a ?? position)}</button>
          <button class="small" onclick={setB} disabled={!loop && position === 0}>B = {loop ? fmt(loop.b) : "—"}</button>
          {#if loop}<button class="small ghost" onclick={() => (loop = null)}>clear</button>{/if}
        </div>
        <p class="muted">{hands.length >= 2 ? "2 hands: right hand blue, left hand green. " : ""}{mode === "play" ? "Hit each note as it reaches the yellow line." : "pisynth plays the song; the notes light up as they sound."}</p>
        <button class="link" onclick={() => { stop(); song = null; options = false; }}>close the song (live keyboard)</button>
      {/if}
    </section>
  {/if}

  <div class="player">
    <button class="play" onclick={() => (playing ? stop() : song ? start() : (options = true))} aria-label={playing ? "Stop" : "Play"}>
      {#if playing}
        <svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5" /></svg>
      {:else}
        <svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z" /></svg>
      {/if}
    </button>
    <div class="meta">
      {#if song}
        <div class="bar">
          {#if loop}<span class="loopzone" style:left={pct(loop.a)} style:width="calc({pct(loop.b)} - {pct(loop.a)})"></span>{/if}
          <input class="seek" type="range" min="0" max={current.durationMs || 1} step="100"
                 value={Math.min(position, current.durationMs)} onchange={seek} aria-label="position">
        </div>
        <div class="time">{fmt(position)} / {fmt(current.durationMs)}{tempo !== 100 ? ` · ${tempo}%` : ""}{loop ? " · loop" : ""}</div>
      {:else}
        <div class="time">No song — play along with the library</div>
      {/if}
    </div>
    <button class="more" class:open={options} onclick={() => (options = !options)} aria-label="song, tempo and loop">
      <svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" /></svg>
    </button>
  </div>
  <Keyboard view={song ? view : null} on={liveOn} demo={guide} height={song ? "clamp(64px, 19vh, 170px)" : "clamp(90px, 30vh, 240px)"} minHeight="64px" />
</main>

<style>
  main { flex: 1; display: flex; flex-direction: column; min-height: 0; }
  .hud { display: flex; align-items: center; gap: 10px; padding: 4px 12px; font-variant-numeric: tabular-nums; min-height: 38px; }
  .toggle { display: flex; background: #2a2a36; border-radius: 999px; padding: 2px; flex: 0 0 auto; }
  .toggle button { margin: 0; padding: 5px 12px; border-radius: 999px; background: none; color: var(--muted); font-size: .85rem; font-weight: 600; }
  .toggle button.on { background: var(--accent); color: #fff; }
  .score { font-weight: 800; font-size: 1.1rem; color: var(--yellow); }
  .streak { font-weight: 700; color: #4fd18b; }
  .acc { color: var(--muted); font-size: .85rem; }
  .song { margin-left: auto; color: var(--muted); font-size: .8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .stage { flex: 1; position: relative; min-height: 0; overflow: hidden; background: linear-gradient(#0d0d12, #17171f); }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
  .live { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 16px; min-height: 0; }
  .chord { font-size: clamp(2.5rem, 14vw, 5rem); font-weight: 800; color: var(--yellow); }
  .notes { font-size: clamp(1rem, 5vw, 1.6rem); color: var(--muted); letter-spacing: 1px; }
  .choose { margin-top: 18px; }
  .count { position: absolute; inset: 0; display: grid; place-items: center; font-size: 5rem; font-weight: 800; color: rgba(255,255,255,.85); pointer-events: none; }
  .flash { position: absolute; left: 50%; bottom: 36px; transform: translateX(-50%); font-weight: 800; font-size: 1.1rem; pointer-events: none;
           animation: rise .6s ease-out forwards; text-shadow: 0 2px 6px #000; white-space: nowrap; }
  .flash small { font-weight: 500; font-size: .75rem; opacity: .8; }
  .flash.perfect { color: #ffd23f; } .flash.good { color: #4fd18b; }
  .flash.early, .flash.late { color: #ff9f5a; } .flash.wrong, .flash.miss { color: #ff6b6b; }
  @keyframes rise { from { opacity: 1; transform: translate(-50%, 0); } to { opacity: 0; transform: translate(-50%, -24px); } }
  .results { position: absolute; left: 16px; right: 16px; top: 50%; transform: translateY(-50%); max-height: calc(100% - 12px); overflow: auto; background: rgba(34,34,46,.95); border-radius: 14px; padding: 14px 18px; text-align: center; }
  .results h2 { font-size: clamp(1.6rem, 9vh, 2.6rem); color: var(--yellow); }
  .results button { margin-top: 8px; }
  .results p { margin-top: 6px; }
  .error, .status-msg { position: absolute; left: 12px; right: 12px; top: 8px; }
  .error { color: #ff7a7a; }
  .status-msg { color: var(--muted); }
  .sheet { margin: 6px 12px; padding: 12px 14px; background: var(--bar); border-radius: 12px; overflow-y: auto; max-height: 70vh; }
  .sheet label { display: block; margin-top: 8px; }
  .sheet input[type="range"] { width: 100%; }
  .sheet p { margin-top: 8px; }
  .link { background: none; color: var(--accent); padding: 4px 0; margin-top: 4px; font-weight: 400; display: block; }
  .loop { display: flex; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .small { margin: 0; padding: 6px 10px; font-size: .85rem; border-radius: 8px; }
  .ghost { background: #3a3a48; }
  .player { display: flex; align-items: center; gap: 10px; padding: 6px 12px; background: var(--bar); }
  .player button { margin: 0; padding: 0; display: grid; place-items: center; flex: 0 0 auto; }
  .play { width: 44px; height: 44px; border-radius: 50%; }
  .play svg { width: 22px; height: 22px; fill: #fff; }
  .more { width: 36px; height: 36px; border-radius: 50%; background: none; }
  .more svg { width: 20px; height: 20px; fill: var(--muted); }
  .more.open svg { fill: var(--accent); }
  .meta { flex: 1; min-width: 0; }
  .bar { position: relative; }
  .loopzone { position: absolute; top: 6px; height: 6px; background: rgba(255,210,63,.35); border-radius: 3px; pointer-events: none; }
  .seek { width: 100%; height: 18px; margin: 0; accent-color: var(--accent); display: block; position: relative; }
  .time { font-size: .75rem; color: var(--muted); font-variant-numeric: tabular-nums; }
</style>
