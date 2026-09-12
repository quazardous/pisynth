<script>
  // Synth settings (#2417): soundfont/preset, levels, output, effects, metronome, keyboard — the
  // box's touch UI applies them (same code paths) and pushes back any change made on the box.
  import { SynthApi, throttle } from "./lib/synthapi.js";

  let { onMessage, send } = $props();
  const api = new SynthApi(obj => send(obj));
  let state = $state(null);
  let catalog = $state(null);
  let error = $state("");
  let openFont = $state("");
  let busy = $state(false);
  // Opening a soundfont scrolls its preset box to the preset in use (not the page itself).
  const revealCurrent = box => {
    const cur = box.querySelector(".current");
    if (cur) box.scrollTop = cur.offsetTop - box.clientHeight / 2 + cur.offsetHeight / 2;
  };
  let pendingOutput = $state(null);               // output change waiting for an in-page confirm

  $effect(() => {
    const off = onMessage(msg => { const s = api.onMessage(msg); if (s) state = s; });
    load();
    return off;
  });

  let retry = 0;
  async function load() {
    const r = await api.get();
    if (r.ok) { state = r.state; catalog = r.catalog; openFont = r.state.font; error = ""; return; }
    error = r.error || "could not read the synth settings";
    if (r.error === "not connected" && retry++ < 40) setTimeout(load, 500);   // socket still opening
  }

  async function set(key, value) {
    const r = await api.set(key, value);
    if (r.state) state = r.state;
    error = r.ok ? "" : r.error;
  }

  const setGain = throttle(v => set("gain", v), 150);
  const setVolume = throttle(v => set("volume", v), 150);
  const setFx = throttle((unit, patch) => set(`fx.${unit}`, patch), 150);
  const setMetro = throttle(patch => set("metronome", patch), 150);

  async function choosePreset(font, bank, prog) { busy = true; await set("preset", { font, bank, prog }); busy = false; }

  function chooseOutput(e) {
    const [kind, id] = e.target.value.split("|");
    pendingOutput = kind === "auto" ? { kind: "auto" } : { kind, id };
  }
  function confirmOutput(ok) {
    if (ok) set("output", pendingOutput);
    pendingOutput = null;
  }
  const outputValue = () => state.output.bt_sink ? `bt|${state.output.bt_sink}` : state.output.soundcard ? `card|${state.output.soundcard}` : "auto|";
  const FX_LABELS = { room: "Room size", damp: "Damping", width: "Width", level: "Level", nr: "Voices", speed: "Speed (Hz)", depth: "Depth (ms)" };
  const step = (lo, hi, unit, key) => (unit === "chorus" && key === "nr") ? 1 : (hi - lo) / 100;
</script>

<main>
  {#if !state || !catalog}
    <section class="card"><p class="muted">{error || "Reading the synth settings…"}</p></section>
  {:else}
    {#if error}<p class="error">{error}</p>{/if}

    <section class="card">
      <h2>Sound</h2>
      {#each catalog.fonts as f (f.file)}
        <button class="font" class:current={state.font === f.file} onclick={() => (openFont = openFont === f.file ? "" : f.file)}>
          {f.label}{#if state.font === f.file}<span class="sub">{state.preset_name}</span>{/if}
        </button>
        {#if openFont === f.file}
          {@const list = f.presets.filter(p => p[0] === 0).length ? f.presets.filter(p => p[0] === 0) : f.presets}
          <div class="presets" {@attach revealCurrent}>
            {#each list as [bank, prog, name] (`${bank}-${prog}`)}
              <button class="preset" class:current={state.font === f.file && state.bank === bank && state.prog === prog}
                      disabled={busy} onclick={() => choosePreset(f.file, bank, prog)}>{name}</button>
            {/each}
          </div>
          {#if list.length > 8}<p class="count muted">{list.length} presets — scroll the list</p>{/if}
        {/if}
      {/each}
      {#if state.loading}<p class="muted">loading the soundfont on pisynth…</p>{/if}
    </section>

    <section class="card">
      <h2>Levels</h2>
      <label>Gain {state.gain.toFixed(1)}
        <input type="range" min={catalog.ranges.gain[0]} max={catalog.ranges.gain[1]} step="0.1" value={state.gain}
               oninput={e => setGain(+e.target.value)}></label>
      {#if state.volume !== null}
        <label>Output volume {state.volume}%
          <input type="range" min="0" max="100" step="1" value={state.volume} oninput={e => setVolume(+e.target.value)}></label>
      {/if}
      <label>Output
        <select value={pendingOutput ? `${pendingOutput.kind}|${pendingOutput.id ?? ""}` : outputValue()} onchange={chooseOutput}>
          <option value="auto|">Auto (USB sound card)</option>
          {#each catalog.outputs as o (o.kind + o.id)}<option value={`${o.kind}|${o.id}`}>{o.kind === "bt" ? "Bluetooth: " : ""}{o.label}</option>{/each}
        </select></label>
      {#if pendingOutput}
        <p class="confirm">Switching the output restarts the sound (a few seconds of silence).
          <button onclick={() => confirmOutput(true)}>Switch</button>
          <button class="ghost" onclick={() => confirmOutput(false)}>Cancel</button></p>
      {/if}
    </section>

    {#each ["reverb", "chorus"] as unit (unit)}
      <section class="card">
        <h2 class="row">{unit === "reverb" ? "Reverb" : "Chorus"}
          <input type="checkbox" checked={state.fx[unit].on} onchange={e => set(`fx.${unit}`, { on: e.target.checked })}></h2>
        {#each Object.entries(catalog.ranges.fx[unit]) as [key, [lo, hi]] (key)}
          <label>{FX_LABELS[key]} {state.fx[unit][key]}
            <input type="range" min={lo} max={hi} step={step(lo, hi, unit, key)} value={state.fx[unit][key]}
                   disabled={!state.fx[unit].on} oninput={e => setFx(unit, { [key]: +e.target.value })}></label>
        {/each}
      </section>
    {/each}

    <section class="card">
      <h2 class="row">Metronome
        <input type="checkbox" checked={state.metronome.running} onchange={e => set("metronome", { running: e.target.checked })}></h2>
      <label>Tempo {state.metronome.bpm} BPM
        <input type="range" min="40" max="240" step="1" value={state.metronome.bpm} oninput={e => setMetro({ bpm: +e.target.value })}></label>
      <label>Beats per bar {state.metronome.beats}
        <input type="range" min="1" max="8" step="1" value={state.metronome.beats} oninput={e => setMetro({ beats: +e.target.value })}></label>
      <label>Click volume {state.metronome.vol}
        <input type="range" min="0" max="100" step="5" value={state.metronome.vol} oninput={e => setMetro({ vol: +e.target.value })}></label>
    </section>

    <section class="card">
      <h2>MIDI keyboard</h2>
      <select value={state.midi_keyboard} onchange={e => set("midi_keyboard", e.target.value)}>
        <option value="">Auto (all keyboards)</option>
        {#each catalog.midi_inputs as name (name)}<option value={name}>{name}</option>{/each}
      </select>
    </section>
  {/if}
</main>

<style>
  main { overflow-y: auto; flex: 1; padding-bottom: 24px; }
  h2 { font-size: 1.05rem; margin-bottom: 8px; }
  .row { display: flex; justify-content: space-between; align-items: center; }
  label { display: block; margin-top: 10px; font-size: .92rem; }
  input[type="range"], select { width: 100%; margin-top: 4px; }
  select { font: inherit; padding: 8px; border-radius: 8px; background: var(--bg); color: var(--fg); border: 1px solid #333; }
  input[type="checkbox"] { width: 22px; height: 22px; }
  button.font, button.preset { display: block; width: 100%; text-align: left; margin-top: 6px; padding: 10px 12px; border-radius: 8px; background: #2c2c3a; font-weight: 600; }
  button.current { outline: 2px solid var(--yellow); }
  /* A GM soundfont has 128+ presets: they scroll inside their own box so the page stays short. */
  .presets { position: relative; margin: 6px 0 0 12px; max-height: min(45vh, 360px); overflow-y: auto; overscroll-behavior: contain;
             padding: 0 6px 6px; border-radius: 8px; background: rgba(0,0,0,.18); }
  .count { font-size: .78rem; margin: 4px 0 0 12px; }
  button.preset { font-weight: 400; padding: 8px 12px; }
  .sub { display: block; font-size: .8rem; color: var(--yellow); font-weight: 400; }
  .error { color: #ff7a7a; margin: 12px 16px 0; }
  .confirm { margin-top: 10px; color: var(--yellow); }
  .confirm button { margin: 8px 8px 0 0; padding: 8px 14px; }
  .ghost { background: #3a3a48; }
</style>
