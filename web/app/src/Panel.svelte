<script>
  // The side panel (#2667): all the navigation in one place, slid in from the left over the stage — the main mode
  // (Score | Game), the secondary one (I play / Listen, normal / hybrid / infinite), the musician, the metronome,
  // effects & points (Score mode), tempo and loop, the gallery (every song and score, every mode), the settings.
  // Closed, the player shrinks to the floating mini player (Player.svelte).
  import Catalog from "./Catalog.svelte";
  import Library from "./Library.svelte";
  import Gauge from "./Gauge.svelte";
  import { prefs, setView, setPlayMode, setScoreFx, setScoreNames, setScoreZoom, PLAY_MODES } from "./lib/prefs.svelte.js";
  import { musicians, selectMusician } from "./lib/musician.svelte.js";
  import { metro, metroLive, toggleMetronome, setBpm } from "./lib/metronome.svelte.js";
  import { nearestPreset } from "./lib/metronome.js";
  import { loadSong } from "./lib/library.js";
  import { sampleSong } from "./lib/midifile.js";
  import { DEMO, demoState, setAutoplay } from "./lib/demobackend.js";

  let autoplay = $state(demoState.autoplay);

  let {
    song = null, mode = "play", onMode = () => {}, onPick, onClose, onPanel = () => {}, link = "",
    tempo = 100, onTempo = () => {}, loop = null, position = 0, onSetA, onSetB, onClearLoop, fmt = x => x,
    parts = [], cleared = 0, onRestartParts = () => {}, onChooseMode = m => setPlayMode(m), lv = null, songDiff = 0,
  } = $props();

  const scoreMode = $derived(prefs.view === "piano");
  const MODE_LABEL = { normal: "Normal", hybrid: "Hybrid", infinite: "Infinite" };
  let entries = $state.raw([]);
  let error = $state("");

  async function pickEntry(entry) {
    error = "";
    try { onPick((await loadSong(entry)).song); } catch (err) { error = err.message; }
  }
</script>

<aside class="panel" aria-label="navigation">
  <div class="top">
    <div class="modeswitch" role="tablist" aria-label="mode">
      <button role="tab" class:on={scoreMode} aria-selected={scoreMode} onclick={() => setView("piano")}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3z" /></svg>Score</button>
      <button role="tab" class:on={!scoreMode} aria-selected={!scoreMode} onclick={() => setView("game")}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 6h10a5 5 0 0 1 0 10c-1.5 0-2.3-.8-3-1.5h-4c-.7.7-1.5 1.5-3 1.5A5 5 0 0 1 7 6zm-.5 3v1.5H5V12h1.5v1.5H8V12h1.5v-1.5H8V9zm9 .5a1 1 0 1 0 0 2 1 1 0 0 0 0-2zm2 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2z" /></svg>Game</button>
    </div>
    <span class="dot" class:on={link === "live"} title="pisynth: {link}"></span>
    <button class="icon" onclick={() => onPanel(DEMO ? "display" : "sound")} aria-label="settings">
      <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94s-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96a7 7 0 0 0-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84a.47.47 0 0 0-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.48.48 0 0 0-.59.22L2.74 8.87a.47.47 0 0 0 .12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.47.47 0 0 0-.12-.61zM12 15.6a3.6 3.6 0 1 1 0-7.2 3.6 3.6 0 0 1 0 7.2z" /></svg>
    </button>
    <button class="icon" onclick={onClose} aria-label="close the panel">
      <svg viewBox="0 0 24 24"><path d="M15.5 4.5 8 12l7.5 7.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>
  </div>

  <div class="scroll">
    {#if DEMO}
      <section class="demo">
        <p><b>Demo</b> — no pisynth here. Play with a MIDI keyboard plugged into this computer, the computer keys
          (<kbd>A</kbd>…<kbd>L</kbd> white, <kbd>W</kbd> <kbd>E</kbd> <kbd>T</kbd>… black, <kbd>Z</kbd>/<kbd>X</kbd> octave) or the keys on screen.
          <a href="https://github.com/quazardous/pisynth">Get pisynth</a></p>
        <label class="switch">
          <input type="checkbox" checked={autoplay} onchange={e => { autoplay = e.target.checked; setAutoplay(autoplay); }}>
          <span>Let the demo play<small>the song is played for you, to watch the game</small></span>
        </label>
      </section>
    {/if}
    <section>
      <div class="row">
        <label class="who" style:--mc={musicians.list.find(m => m.id === musicians.current)?.color}>
          <select value={musicians.current} onchange={e => selectMusician(e.target.value)} aria-label="who is playing">
            {#each musicians.list as m (m.id)}<option value={m.id}>{m.name}</option>{/each}
          </select>
        </label>
        {#if lv && (!scoreMode || prefs.scoreFx)}<span class="lv">Lv {lv.level}<i style:width="{Math.round((lv.into / lv.need) * 100)}%"></i></span>{/if}
      </div>

      {#if scoreMode}
        <label class="switch">
          <input type="checkbox" checked={prefs.scoreFx} onchange={e => setScoreFx(e.target.checked)}>
          <span>Effects & points<small>combos, explosions, points and XP while you play the score</small></span>
        </label>
        <label class="switch">
          <input type="checkbox" checked={prefs.scoreNames} onchange={e => setScoreNames(e.target.checked)}>
          <span>Note names<small>under each note of the score ({prefs.notation === "fr" ? "Do Ré Mi" : "C D E"})</small></span>
        </label>
        <label class="zoom">Score size {prefs.scoreZoom > 0 ? "+" : ""}{prefs.scoreZoom}%
          <span class="zoomrow">
            <input type="range" min="-100" max="100" step="10" value={prefs.scoreZoom} oninput={e => setScoreZoom(+e.target.value)}>
            {#if prefs.scoreZoom}<button class="link" onclick={() => setScoreZoom(0)}>reset</button>{/if}
          </span>
        </label>
      {:else}
        <div class="seg" role="group" aria-label="I play or listen">
          <button class:on={mode === "play"} onclick={() => onMode("play")}>I play</button>
          <button class:on={mode === "listen"} onclick={() => onMode("listen")}>Listen</button>
        </div>
        {#if mode === "play"}
          <div class="seg" role="radiogroup" aria-label="play mode">
            {#each PLAY_MODES as m (m)}
              <button class:on={prefs.playMode === m} role="radio" aria-checked={prefs.playMode === m} onclick={() => onChooseMode(m)}>{MODE_LABEL[m]}</button>
            {/each}
          </div>
          {#if prefs.playMode === "hybrid" && parts.length}
            <p class="muted small">{cleared} of {parts.length} parts cleared{#if cleared} · <button class="link" onclick={onRestartParts}>start over from part 1</button>{/if}</p>
          {/if}
        {/if}
      {/if}
    </section>

    {#if scoreMode}
      <section class="metro">
        <button class="go" class:on={metroLive.running} onclick={toggleMetronome} aria-label="metronome">
          <svg viewBox="0 0 24 24"><path d="M9.2 2h5.6l4.4 18.5A1.2 1.2 0 0 1 18 22H6a1.2 1.2 0 0 1-1.2-1.5zM7.4 16h9.2l-.9-3.8-3.2 3.2-1.3-1.3 3.9-3.9L13.2 4h-2.4z" /></svg>
        </button>
        <button class="step" onclick={() => setBpm(metro.bpm - 1)} aria-label="slower">−</button>
        <span class="bpm"><b>{metro.bpm}</b><small>{nearestPreset(metro.bpm)[0]}</small></span>
        <button class="step" onclick={() => setBpm(metro.bpm + 1)} aria-label="faster">+</button>
        <button class="link more" onclick={() => onPanel("metronome")}>more…</button>
      </section>
    {/if}

    {#if song}
      <section class="song">
        <p class="name">{song.name || "untitled"}{#if song.credit}<small>{song.credit}</small>{/if}</p>
        {#if !scoreMode}
          <label>Tempo {Math.round(tempo)}% <input type="range" min="50" max="150" step="5" value={tempo} onchange={e => onTempo(+e.target.value)}></label>
        {/if}
        <div class="loop">
          <span>Loop</span>
          <button class="small" onclick={onSetA}>A = {fmt(loop?.a ?? position)}</button>
          <button class="small" onclick={onSetB} disabled={!loop && position === 0}>B = {loop ? fmt(loop.b) : "—"}</button>
          {#if loop}<button class="small ghost" onclick={onClearLoop}>clear</button>{/if}
        </div>
        {#if !scoreMode}<p class="muted small">Difficulty <Gauge value={songDiff} number /></p>{/if}
      </section>
    {/if}

    <section class="gallery">
      <h2>Gallery</h2>
      <Catalog {onPick} current={song?.path ?? ""} {entries} onPickEntry={pickEntry} />
      {#if error}<p class="error">{error}</p>{/if}
      <details>
        <summary>Folders</summary>
        <Library {onPick} current={song?.path ?? ""} onEntries={e => (entries = e)} />
        <button class="link" onclick={() => onPick(sampleSong())}>use the built-in sample</button>
      </details>
    </section>
  </div>
</aside>

<style>
  .panel { position: absolute; left: 0; top: 0; bottom: 0; z-index: 20; width: min(100%, clamp(300px, 38vw, 420px)); display: flex; flex-direction: column;
           background: var(--bar); box-shadow: 8px 0 24px rgba(0,0,0,.45); padding-left: env(safe-area-inset-left, 0); }
  .top { display: flex; align-items: center; gap: 8px; padding: max(8px, env(safe-area-inset-top, 0)) 8px 8px 10px; border-bottom: 1px solid #2c2c3a; }
  .modeswitch { display: flex; background: #17171f; border-radius: 999px; padding: 3px; gap: 2px; }
  .modeswitch button { margin: 0; display: flex; align-items: center; gap: 5px; padding: 6px 11px; border-radius: 999px; background: none;
                       color: var(--muted); font-size: .85rem; font-weight: 700; }
  .modeswitch svg { width: 17px; height: 17px; fill: currentColor; }
  .modeswitch button.on { background: var(--accent); color: #fff; }
  .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--muted); margin-left: auto; flex: 0 0 auto; }
  .dot.on { background: #0c0; }
  .icon { margin: 0; padding: 6px; background: none; color: var(--muted); display: grid; place-items: center; border-radius: 50%; }
  .icon svg { width: 22px; height: 22px; fill: currentColor; }
  .scroll { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 4px 12px max(12px, env(safe-area-inset-bottom, 0)); }
  section { padding: 10px 0; border-bottom: 1px solid #2c2c3a; }
  section:last-child { border-bottom: 0; }
  h2 { font-size: .8rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 4px; }
  .row { display: flex; align-items: center; gap: 10px; }
  .who { position: relative; flex: 1; min-width: 0; height: 36px; border-radius: 18px; overflow: hidden; border: 2px solid var(--mc, #c38bff);
         background: linear-gradient(rgba(18,18,24,.62), rgba(18,18,24,.62)), var(--mc, #c38bff); }
  .who::after { content: ""; position: absolute; right: 12px; top: 50%; width: 7px; height: 7px; pointer-events: none;
                border-right: 2px solid var(--mc, #c38bff); border-bottom: 2px solid var(--mc, #c38bff); transform: translateY(-70%) rotate(45deg); }
  .who select { -webkit-appearance: none; appearance: none; width: 100%; height: 100%; margin: 0; padding: 0 30px 0 14px; border: 0; outline: none;
                background: transparent; color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
  .who option { color: #121218; background: #fff; }
  .lv { position: relative; font-weight: 800; color: #c38bff; font-size: .9rem; padding-bottom: 3px; }
  .lv i { position: absolute; left: 0; bottom: 0; height: 2px; background: #c38bff; }
  .seg { display: flex; gap: 3px; background: #17171f; border-radius: 999px; padding: 3px; margin-top: 8px; }
  .seg button { flex: 1; margin: 0; padding: 7px 0; border-radius: 999px; background: none; color: var(--muted); font-size: .85rem; font-weight: 700; }
  .seg button.on { background: var(--accent); color: #fff; }
  .switch { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
  .switch input { width: 22px; height: 22px; flex: 0 0 auto; }
  .switch small { display: block; color: var(--muted); font-size: .75rem; }
  .demo p { font-size: .82rem; line-height: 1.45; }
  .demo a { color: var(--accent); }
  kbd { font: 700 .72rem system-ui, sans-serif; padding: 0 4px; border-radius: 4px; background: #3a3a48; }
  .zoom { display: block; margin-top: 10px; font-size: .85rem; }
  .zoomrow { display: flex; align-items: center; gap: 8px; }
  .zoomrow input { flex: 1; }
  .metro { display: flex; align-items: center; gap: 8px; }
  .metro .go { margin: 0; width: 42px; height: 42px; padding: 0; border-radius: 50%; background: #2c2c3a; color: var(--muted); display: grid; place-items: center; }
  .metro .go svg { width: 22px; height: 22px; fill: currentColor; }
  .metro .go.on { background: var(--accent); color: #fff; }
  .step { margin: 0; width: 34px; height: 34px; padding: 0; border-radius: 50%; background: #2c2c3a; font-size: 1.2rem; }
  .bpm { display: flex; flex-direction: column; align-items: center; min-width: 4.5ch; line-height: 1.1; }
  .bpm b { font-size: 1.3rem; font-variant-numeric: tabular-nums; }
  .bpm small { font-size: .65rem; color: var(--muted); }
  .more { margin-left: auto; }
  .song .name { font-weight: 700; }
  .song .name small { display: block; font-weight: 400; font-size: .72rem; color: var(--muted); }
  .song label { display: block; margin-top: 8px; font-size: .85rem; }
  .song input[type="range"] { width: 100%; }
  .loop { display: flex; align-items: center; gap: 6px; margin-top: 8px; font-size: .85rem; flex-wrap: wrap; }
  .small { margin: 0; padding: 5px 9px; font-size: .8rem; border-radius: 8px; }
  .ghost { background: #3a3a48; }
  .link { margin: 0; padding: 0; background: none; color: var(--accent); font-weight: 600; font-size: .85rem; }
  p.small { font-size: .78rem; margin-top: 6px; }
  details { margin-top: 10px; }
  summary { cursor: pointer; color: var(--muted); font-weight: 700; font-size: .85rem; padding: 4px 0; }
  .gallery :global(.list) { max-height: none; }
  .error { color: #ff7a7a; font-size: .85rem; margin-top: 6px; }
</style>
