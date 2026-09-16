// The metronome managed from the companion (#2658), shared by every screen (see lib/metronome.js).
// While the phone is connected it drives pisynth's metronome: the musician's tempo is handed over when they
// pick up the phone, the click is played by pisynth or by the phone (then pisynth only counts the beats, and
// Start/Stop on its screen starts the phone's click), and changes on either side show on both.

import { SynthApi, throttle } from "./synthapi.js";
import { loadMetro, saveMetro, clampBpm, clampBeats, clampVol, gridBeat, tapTempo } from "./metronome.js";
import { startClicker } from "./metroclick.js";
import { audioContext } from "./click.js";
import { storeKey, onMusicianChange } from "./musician.svelte.js";

const KEY = "pisynth.metronome";
const storage = () => globalThis.localStorage;

export const metro = $state(loadMetro(storage(), storeKey(KEY)));       // this musician's settings
export const metroLive = $state({ connected: false, running: false, beat: 0, error: "" });

let api = null, synced = false, clicker = null, grid = null, taps = [], lastLocal = -Infinity;
const save = () => saveMetro(metro, storage(), storeKey(KEY));
const settings = () => ({ bpm: metro.bpm, beats: metro.beats, vol: metro.vol });

async function request(value, tries = 3) {
  if (!api) return;
  const r = await api.set("metronome", value);
  // pisynth-web tells the box a phone is here a moment after it connects: ask again
  if (!r.ok && r.error === "no web companion connected" && tries > 1) { setTimeout(() => request(value, tries - 1), 800); return; }
  metroLive.error = r.ok ? "" : r.error || "";
  if (r.state) onState(r.state);
}
const pushSettings = throttle(() => { lastLocal = performance.now(); request(settings()); }, 150);

// The beat lights (and the phone's click) on a grid starting now, like pisynth's click starting over.
function regrid() {
  grid = { anchor: performance.now() + 60, beatMs: 60000 / metro.bpm, beats: metro.beats, first: 1 };
  clicker?.replan();
}
function run(on) {
  metroLive.running = on;
  if (on && !clicker) {
    regrid();
    clicker = startClicker({
      nextBeat: t => gridBeat(grid, t),
      sound: () => metro.by === "phone" && metroLive.connected,
      vol: () => metro.vol,
      onBeat: n => (metroLive.beat = n),
    });
  } else if (!on && clicker) {
    clicker.stop(); clicker = null; metroLive.beat = 0;
  }
}

function onState(state) {
  const pi = state?.metronome;
  if (!pi) return;
  if (!synced) {                                   // just connected: pisynth takes this musician's metronome
    synced = true;
    request({ ...settings(), silent: metro.by === "phone" });
  } else if (performance.now() - lastLocal > 700) {   // changed elsewhere (Sound panel, pisynth): follow it
    const changed = pi.bpm !== metro.bpm || pi.beats !== metro.beats;
    if (changed || pi.vol !== metro.vol) {
      Object.assign(metro, { bpm: clampBpm(pi.bpm), beats: clampBeats(pi.beats), vol: clampVol(pi.vol) });
      save();
      if (changed && clicker) regrid();
    }
  }
  run(!!pi.running);
}

// App: the companion socket is there (once).
export function attachMetronome({ onMessage, send }) {
  api = new SynthApi(send);
  return onMessage(msg => { const s = api.onMessage(msg); if (s) onState(s); });
}

// App: the link to pisynth came up or dropped.
export async function metronomeLink(live) {
  metroLive.connected = live;
  if (!live) { synced = false; run(false); return; }
  const r = await api?.get();
  if (r?.ok) onState(r.state);
}

onMusicianChange(() => {
  Object.assign(metro, loadMetro(storage(), storeKey(KEY)));
  if (synced) { lastLocal = performance.now(); request({ ...settings(), silent: metro.by === "phone" }); }
  if (clicker) regrid();
});

// ---- controls (from a tap: the phone may start its audio) ----
export function toggleMetronome() {
  if (metro.by === "phone") audioContext();
  const on = !metroLive.running;
  run(on);
  lastLocal = performance.now();
  request({ ...settings(), silent: metro.by === "phone", running: on });
}

export function setBpm(v) {
  const bpm = clampBpm(v);
  if (bpm === metro.bpm) return;
  metro.bpm = bpm; save();
  if (clicker) regrid();
  pushSettings();
}

export function setBeats(v) {
  const beats = clampBeats(v);
  if (beats === metro.beats) return;
  metro.beats = beats; save();
  if (clicker) regrid();
  pushSettings();
}

export function setMetroVol(v) {
  metro.vol = clampVol(v); save();
  pushSettings();
}

export function tapBeat() {
  const r = tapTempo(taps, performance.now());
  taps = r.taps;
  if (r.bpm) setBpm(r.bpm);
  return r.bpm;
}

export function setClickBy(by) {
  metro.by = by === "phone" ? "phone" : "pisynth";
  save();
  if (metro.by === "phone") audioContext();
  lastLocal = performance.now();
  request({ silent: metro.by === "phone" });
}

export function setClickInPlayer(on) {
  metro.inPlayer = !!on;
  save();
  if (on) audioContext();
}
