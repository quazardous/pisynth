<script>
  // The metronome, from the companion (#2658): start/stop, tempo (−/+, slider, tap, the classic markings),
  // beats per bar, the beat lights, and who plays the click. Each musician keeps theirs (lib/metronome.svelte.js).
  import { TEMPO_PRESETS, BPM, BEATS, nearestPreset } from "./lib/metronome.js";
  import { metro, metroLive, toggleMetronome, setBpm, setBeats, setMetroVol, tapBeat, setClickBy, setClickInPlayer } from "./lib/metronome.svelte.js";
  import { currentMusician } from "./lib/musician.svelte.js";

  let tapped = $state(false);
  function tap() {
    tapBeat();
    tapped = true;
    setTimeout(() => (tapped = false), 120);
  }
</script>

<main>
  <section class="card metro">
    <div class="lights" style:--n={metro.beats}>
      {#each Array.from({ length: metro.beats }, (_, i) => i + 1) as n (n)}
        <span class:on={metroLive.beat === n} class:one={n === 1}></span>
      {/each}
    </div>

    <div class="tempo">
      <button class="step" onclick={() => setBpm(metro.bpm - 1)} aria-label="slower">−</button>
      <div class="bpm"><b>{metro.bpm}</b><small>BPM · {nearestPreset(metro.bpm)[0]}</small></div>
      <button class="step" onclick={() => setBpm(metro.bpm + 1)} aria-label="faster">+</button>
    </div>
    <input class="slider" type="range" min={BPM[0]} max={BPM[1]} step="1" value={metro.bpm} oninput={e => setBpm(+e.target.value)} aria-label="tempo">

    <div class="actions">
      <button class="go" class:on={metroLive.running} onclick={toggleMetronome} disabled={!metroLive.connected}>
        {metroLive.running ? "Stop" : "Start"}</button>
      <button class="tap" class:hit={tapped} onpointerdown={tap}>Tap</button>
    </div>
    {#if metroLive.error}<p class="error">{metroLive.error}</p>{/if}
    {#if !metroLive.connected}<p class="muted">Waiting for pisynth…</p>{/if}

    <div class="presets">
      {#each TEMPO_PRESETS as [name, bpm] (name)}
        <button class:on={nearestPreset(metro.bpm)[1] === bpm} onclick={() => setBpm(bpm)}>{name}<small>{bpm}</small></button>
      {/each}
    </div>
  </section>

  <section class="card">
    <div class="row">
      <span>Beats per bar</span>
      <span class="stepper">
        <button onclick={() => setBeats(metro.beats - 1)} disabled={metro.beats <= BEATS[0]} aria-label="fewer beats">−</button>
        <b>{metro.beats}</b>
        <button onclick={() => setBeats(metro.beats + 1)} disabled={metro.beats >= BEATS[1]} aria-label="more beats">+</button>
      </span>
    </div>
    <label class="vol">Click volume {metro.vol}
      <input type="range" min="0" max="100" step="5" value={metro.vol} oninput={e => setMetroVol(+e.target.value)}></label>
  </section>

  <section class="card">
    <h1>Click played by</h1>
    {#each [["pisynth", "pisynth", "Through the synth's speakers, with the piano. This phone is the remote."],
            ["phone", "This phone", "The phone clicks (in your headphones, say); pisynth only counts the beats on its screen."]] as [id, label, text] (id)}
      <label class="choice">
        <input type="radio" name="clickby" checked={metro.by === id} onchange={() => setClickBy(id)}>
        <span>{label}<br><small class="muted">{text}</small></span>
      </label>
    {/each}
    <label class="choice">
      <input type="checkbox" checked={metro.inPlayer} onchange={e => setClickInPlayer(e.target.checked)}>
      <span>Click along with songs<br><small class="muted">In the player, this phone clicks at the song's tempo and time signature.
        Also with the metronome button in the player bar.</small></span>
    </label>
    <p class="muted note">Saved for {currentMusician().name}. While the companion is connected, the pisynth screen keeps only Start / Stop.</p>
  </section>
</main>

<style>
  .metro { text-align: center; }
  .lights { display: grid; grid-template-columns: repeat(var(--n), 1fr); gap: 10px; max-width: 360px; margin: 4px auto 14px; }
  .lights span { height: 22px; border-radius: 11px; background: #2c2c3a; transition: background .06s, transform .06s; }
  .lights span.on { background: var(--accent); transform: scaleY(1.25); }
  .lights span.one.on { background: var(--yellow); }
  .tempo { display: flex; align-items: center; justify-content: center; gap: 18px; }
  .step { margin: 0; width: 56px; height: 56px; padding: 0; border-radius: 50%; background: #2c2c3a; font-size: 1.8rem; line-height: 1; }
  .bpm { display: flex; flex-direction: column; min-width: 7ch; }
  .bpm b { font-size: 3.6rem; line-height: 1; font-variant-numeric: tabular-nums; }
  .bpm small { color: var(--muted); font-weight: 600; }
  .slider { width: 100%; margin-top: 14px; }
  .actions { display: flex; gap: 12px; justify-content: center; }
  .actions button { flex: 1; max-width: 180px; font-size: 1.2rem; padding: 16px 0; }
  .go { background: #4fd18b; color: #121218; }
  .go.on { background: #ff5a5a; color: #fff; }
  .go:disabled { opacity: .4; }
  .tap { background: #2c2c3a; touch-action: manipulation; }
  .tap.hit { background: var(--accent); }
  .presets { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin-top: 14px; }
  .presets button { margin: 0; padding: 6px 10px; border-radius: 999px; background: #2c2c3a; color: var(--fg); font-size: .85rem;
                    display: flex; gap: 5px; align-items: baseline; }
  .presets button small { color: var(--muted); font-weight: 600; }
  .presets button.on { background: var(--yellow); color: #121218; }
  .presets button.on small { color: #121218; }
  .row { display: flex; align-items: center; justify-content: space-between; }
  .stepper { display: flex; align-items: center; gap: 14px; }
  .stepper button { margin: 0; width: 40px; height: 40px; padding: 0; border-radius: 50%; background: #2c2c3a; font-size: 1.3rem; }
  .stepper button:disabled { opacity: .35; }
  .stepper b { font-size: 1.4rem; min-width: 1.5ch; text-align: center; }
  .vol { display: block; margin-top: 14px; }
  .vol input { width: 100%; }
  .choice { display: flex; align-items: center; gap: 12px; margin-top: 12px; text-align: left; }
  .choice input { width: 22px; height: 22px; flex: 0 0 auto; }
  .note { margin-top: 14px; }
  .error { color: #ff7a7a; margin-top: 8px; }
</style>
