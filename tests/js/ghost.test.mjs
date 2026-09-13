import test from "node:test";
import assert from "node:assert/strict";
import { ghostKeys, ghostPulses, sameSet } from "../../web/app/src/lib/ghost.js";
import { longestNote } from "../../web/app/src/lib/highway.js";
import { ClockSync } from "../../web/app/src/lib/clock.js";

const notes = [
  { note: 60, start: 1000, end: 1500 }, { note: 64, start: 1000, end: 1500 },   // a chord
  { note: 67, start: 1500, end: 1510 },                                         // very short
  { note: 60, start: 1600, end: 2000 },                                         // same key again
];
const max = longestNote(notes);

test("ghost keys follow the score exactly: no head start, chords, short notes, repeated keys", () => {
  assert.deepEqual([...ghostKeys(notes, 999, max)], []);                       // not a ms early
  assert.deepEqual([...ghostKeys(notes, 1000, max)].sort(), [60, 64]);
  assert.deepEqual([...ghostKeys(notes, 1499, max)].sort(), [60, 64]);
  assert.deepEqual([...ghostKeys(notes, 1500, max)], [67]);                     // released at the end
  assert.deepEqual([...ghostKeys(notes, 1540, max)], [67]);                     // 10 ms note held 45 ms
  assert.deepEqual([...ghostKeys(notes, 1550, max)], []);
  assert.deepEqual([...ghostKeys(notes, 1600, max)], [60]);
  assert.deepEqual([...ghostKeys(notes, 1540, max, 20)], []);                   // min scaled by tempo
});

test("pulses: notes whose start was crossed within the window, with their age", () => {
  assert.deepEqual(ghostPulses(notes, 1100, max, 180), [{ note: 60, age: 100 }, { note: 64, age: 100 }]);
  assert.deepEqual(ghostPulses(notes, 1200, max, 180), []);
  assert.ok(sameSet(new Set([1, 2]), new Set([2, 1])) && !sameSet(new Set([1]), new Set([1, 2])));
});

test("typical lag: median extra delay over the fastest trip", () => {
  const c = new ClockSync();
  assert.equal(c.typicalLag(), 0);
  [[0, 1000], [100, 1105], [200, 1230], [300, 1310], [400, 1408]].forEach(([pi, local]) => c.observe(pi, local));
  assert.equal(c.offset, 1000);                                                 // fastest: 0 ms extra
  assert.equal(c.typicalLag(), 8);                                              // extras 0,5,30,10,8 → 8
});

test("count-in ticks on the phone: n beats ending where the song starts", async () => {
  const { countInTimes } = await import("../../web/app/src/lib/click.js");
  assert.deepEqual(countInTimes(5000, 500, 4), [3000, 3500, 4000, 4500]);
  assert.deepEqual(countInTimes(3000, 500), [1500, 2000, 2500]);                  // default 3 · 2 · 1
  assert.deepEqual(countInTimes(1000, 250, 2), [500, 750]);
});
