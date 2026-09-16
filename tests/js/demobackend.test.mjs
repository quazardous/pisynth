// The GitHub Pages demo's stand-in for pisynth (#2669): API routes to static files, computer keys, frames, the demo's playing.
import test from "node:test";
import assert from "node:assert/strict";
import { demoRoute, keyNote, encodeFrame, simEvents, DEMO } from "../../web/app/src/lib/demobackend.js";
import { decodeFrame } from "../../web/app/src/lib/midi.js";

test("not a demo outside the demo build", () => assert.equal(DEMO, false));

test("the API answered from static files", () => {
  assert.deepEqual(demoRoute("/api/session"), { session: true });
  assert.deepEqual(demoRoute("/api/midi"), { static: "demo/library.json" });
  assert.deepEqual(demoRoute("/api/midi/starter/0-homer/7-Ode-to-joy.mid"), { static: "demo/library/starter/0-homer/7-Ode-to-joy.mid" });
  assert.deepEqual(demoRoute("/api/catalog?q=chopin&level=2"), { search: "/api/catalog?q=chopin&level=2" });
  assert.deepEqual(demoRoute("/api/catalog/123.mxl"), { static: "demo/catalog/123.mxl" });
  assert.deepEqual(demoRoute("/metronome-tick.wav"), { static: "metronome-tick.wav" });
  assert.deepEqual(demoRoute("/api/midi?dir=x&name=a.mid", "POST"), { refused: true });
  assert.deepEqual(demoRoute("/api/midi/x.mid", "DELETE"), { refused: true });
  assert.equal(demoRoute("/pisynth/assets/index.js"), null);
});

test("computer keys laid out like a piano", () => {
  assert.equal(keyNote("a"), 60);
  assert.equal(keyNote("W"), 61);
  assert.equal(keyNote("k"), 72);
  assert.equal(keyNote("a", -1), 48);
  assert.equal(keyNote("q"), null);
});

test("frames as pisynth sends them", () => {
  assert.deepEqual(decodeFrame(encodeFrame(0x90, 60, 100, 12345.6)), { type: "on", note: 60, velocity: 100, channel: 0, t: 12346 });
  assert.equal(decodeFrame(encodeFrame(0x80, 60, 0, 1)).type, "off");
});

test("the demo plays along, a little human, in order", () => {
  let k = 0;
  const random = () => [0.5, 0.2, 0.9, 0.5, 0.5, 0.1][k++ % 6];
  const ev = simEvents([[0, 400, 60], [500, 900, 62]], 1000, { skill: 0.9, random });
  assert.equal(ev.length, 4);
  assert.deepEqual(ev.map(e => [e[1], e[2]]), [[true, 60], [false, 60], [true, 62], [false, 62]]);
  assert.ok(ev.every((e, i) => i === 0 || e[0] >= ev[i - 1][0]));
  assert.ok(Math.abs(ev[0][0] - 1000) <= 18 && ev[2][0] > 1400);
});
