// The companion's metronome (#2658): tempo markings, tap tempo, beat grids, per-musician settings.
import test from "node:test";
import assert from "node:assert/strict";
import { nearestPreset, tapTempo, gridBeat, songBeat, loadMetro, saveMetro, METRO_DEFAULTS, clampBpm } from "../../web/app/src/lib/metronome.js";
import { SynthApi } from "../../web/app/src/lib/synthapi.js";

const memory = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }; };

test("tempo markings and clamping", () => {
  assert.deepEqual(nearestPreset(80), ["Andante", 92]);
  assert.deepEqual(nearestPreset(300), ["Presto", 184]);
  assert.equal(clampBpm(12), 40);
  assert.equal(clampBpm("nope"), 100);
});

test("tap tempo averages the taps and starts over after a pause", () => {
  let r = tapTempo([], 0);
  assert.equal(r.bpm, null);
  r = tapTempo(r.taps, 500);
  assert.equal(r.bpm, 120);
  r = tapTempo(r.taps, 1000);
  r = tapTempo(r.taps, 1600);                                         // a bit late: average 533 ms
  assert.equal(r.bpm, 112);
  r = tapTempo(r.taps, 5000);                                         // after a pause: a new count
  assert.deepEqual(r, { taps: [5000], bpm: null });
});

test("a steady grid counts the beats of the bar", () => {
  const grid = { anchor: 1000, beatMs: 500, beats: 3 };
  assert.deepEqual(gridBeat(grid, 0), { at: 1000, n: 1 });            // before the start: the first beat
  assert.deepEqual(gridBeat(grid, 1000), { at: 1500, n: 2 });         // strictly after
  assert.deepEqual(gridBeat(grid, 2400), { at: 2500, n: 1 });
});

test("the song's grid: beats on song time, bar lines, only from the start to the end", () => {
  // song at half speed, started at song time 1000 at phone time 5000
  const toSong = t => 1000 + (t - 5000) * 0.5, toLocal = s => 5000 + (s - 1000) / 0.5;
  const g = { beatMs: 500, beatsPerBar: 4, fromMs: 1000, toMs: 3000, toSong, toLocal };
  assert.deepEqual(songBeat(g, 0), { at: 5000, n: 3 });               // count-in: nothing before the start
  let t = 0, seen = [];
  for (let b; (b = songBeat(g, t)); t = b.at) seen.push(b.n);
  assert.deepEqual(seen, [3, 4, 1, 2, 3]);                            // song time 1000, 1500 … 3000, then nothing
  assert.equal(songBeat({ ...g, fromMs: 0 }, 0).at, toLocal(0));      // a quiet restart bar clicks too
});

test("settings are kept per musician, broken ones fall back to the defaults", () => {
  const s = memory();
  assert.deepEqual(loadMetro(s, "k"), METRO_DEFAULTS);
  saveMetro({ by: "phone", bpm: 72, beats: 3, vol: 40, inPlayer: true, junk: 1 }, s, "k");
  assert.deepEqual(loadMetro(s, "k"), { by: "phone", bpm: 72, beats: 3, vol: 40, inPlayer: true });
  s.setItem("k", JSON.stringify({ by: "radio", bpm: 999, beats: 0 }));
  assert.deepEqual(loadMetro(s, "k"), { ...METRO_DEFAULTS, bpm: 240, beats: 1 });
  s.setItem("k", "{broken");
  assert.deepEqual(loadMetro(s, "k"), METRO_DEFAULTS);
});

test("two synth API users never mix up their replies", async () => {
  const sent = [];
  const a = new SynthApi(m => sent.push(m)), b = new SynthApi(m => sent.push(m));
  const pa = a.get(), pb = b.set("metronome", { bpm: 90 });
  assert.notEqual(sent[0].req, sent[1].req);
  for (const api of [a, b]) api.onMessage({ t: "synth", req: sent[1].req, ok: true, who: "b" });
  for (const api of [a, b]) api.onMessage({ t: "synth", req: sent[0].req, ok: true, who: "a" });
  assert.equal((await pa).who, "a");
  assert.equal((await pb).who, "b");
});
