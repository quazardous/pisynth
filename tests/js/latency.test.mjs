import test from "node:test";
import assert from "node:assert/strict";
import { measureLatency, pairHits, summarize } from "../../web/app/src/lib/latency.js";

// Deterministic PRNG for reproducible noise.
function rng(seed) { return () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296) - 0.5; }

function synth({ sr = 48000, gapsMs, periodMs = 700, noise = 0.01, clickAmp = 0.35, noteAmp = 0.7 }) {
  const out = new Float32Array(Math.round(sr * (periodMs * gapsMs.length + 500) / 1000));
  const r = rng(7);
  for (let i = 0; i < out.length; i++) out[i] = noise * r();
  gapsMs.forEach((gap, k) => {
    const c = Math.round(sr * (200 + k * periodMs) / 1000);
    for (let i = 0; i < sr * 0.002; i++) out[c + i] += clickAmp * r() * 2;             // 2 ms broadband click
    const n = c + Math.round(sr * gap / 1000);
    for (let i = 0; i < sr * 0.3; i++) out[n + i] += noteAmp * Math.exp(-i / (sr * 0.12)) * Math.sin(2 * Math.PI * 262 * i / sr);
  });
  return out;
}

test("recovers the key→sound gap from a synthetic recording", () => {
  const gaps = [22, 25, 24, 23, 26, 24, 25, 23, 24, 25];
  const res = measureLatency(synth({ gapsMs: gaps }), 48000);
  assert.equal(res.n, 10);
  assert.ok(Math.abs(res.median - 24) <= 2, `median ${res.median}`);
});

test("works at 44.1 kHz and with a quieter click", () => {
  const res = measureLatency(synth({ sr: 44100, gapsMs: [40, 41, 39, 40, 42, 40], clickAmp: 0.15 }), 44100);
  assert.ok(res.n >= 5, `hits ${res.n}`);
  assert.ok(Math.abs(res.median - 40) <= 2, `median ${res.median}`);
});

test("pairing ignores hits without a note in the window and summarize drops outliers", () => {
  const onsets = [{ t: 0, peak: 1 }, { t: 30, peak: 5 }, { t: 1000, peak: 1 }, { t: 2000, peak: 1 }, { t: 2400, peak: 6 }];
  assert.deepEqual(pairHits(onsets), [30]);
  const s = summarize([24, 25, 23, 24, 90]);
  assert.equal(s.used, 4);
  assert.equal(s.median, 24);
  assert.equal(summarize([]).median, null);
});
