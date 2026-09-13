import test from "node:test";
import assert from "node:assert/strict";
import { rng, burstPath, comboSplash, oopsSplash } from "../../web/app/src/lib/comic.js";
import { Judge } from "../../web/app/src/lib/judge.js";

test("comic bursts: seeded, closed, alternating spikes inside the box", () => {
  assert.equal(burstPath(42), burstPath(42));
  assert.notEqual(burstPath(42), burstPath(43));
  const path = burstPath(7, { w: 200, h: 120, spikes: 12 });
  assert.match(path, /^M.*Z$/);
  const pts = path.slice(1, -1).split("L").map(p => p.split(",").map(Number));
  assert.equal(pts.length, 24);
  const dist = ([x, y]) => Math.hypot((x - 100) / 100, (y - 60) / 60);
  for (const p of pts) assert.ok(dist(p) <= 1.001, `outside the ellipse: ${p}`);
  for (let i = 0; i < pts.length; i += 2) assert.ok(dist(pts[i]) > dist(pts[i + 1]) - 0.05);   // spike, then notch
  const r = rng(1); for (let i = 0; i < 100; i++) { const v = r(); assert.ok(v >= 0 && v < 1); }
});

test("combo splashes vary in size, place and tilt, in the tier colour; the breaker is red", () => {
  const all = Array.from({ length: 40 }, (_, i) => comboSplash(i + 1));
  assert.ok(new Set(all.map(s => s.scale.toFixed(2))).size > 10);
  assert.ok(all.every(s => s.scale >= 0.85 && s.scale <= 1.3 && Math.abs(s.dx) <= 20 && Math.abs(s.tilt) <= 15));
  assert.equal(comboSplash(3, { color: "#5ad1ff" }).color, "#5ad1ff");
  assert.equal(comboSplash(3, { breaker: true }).color, "#ff3b3b");
  assert.deepEqual(oopsSplash(5, 25).word + oopsSplash(5, 25).caption, "OOPS!−25");
  assert.equal(oopsSplash(5, 0).caption, "");
  assert.ok(new Judge([]).press(60, 0).penalty === 0);
});
