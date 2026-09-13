import test from "node:test";
import assert from "node:assert/strict";
import { ComboTracker, ParticlePool, RollingNumber, TIERS, BREAKER_MIN_HITS } from "../../web/app/src/lib/arcade.js";

test("combos: perfects count double, tiers are announced once each, a miss breaks it", () => {
  const c = new ComboTracker();
  assert.equal(c.onResult("good").announce, undefined);            // power 1
  const r = c.onResult("perfect");                                  // power 3 → TRIPLE
  assert.equal(r.hits, 2);
  assert.deepEqual(r.announce, { text: "TRIPLE COMBO", color: TIERS[0][2], tier: 0 });
  assert.equal(c.onResult("good").announce, undefined);            // power 4
  assert.equal(c.onResult("good").announce.text, "SUPER COMBO");   // power 5
  assert.equal(c.onResult("perfect").announce, undefined);         // power 7
  assert.equal(c.onResult("perfect").announce.text, "HYPER COMBO");  // power 9 (skips nothing, 8 crossed)
  assert.equal(c.hits, 6);
  const broke = c.onResult("miss");
  assert.deepEqual(broke, { hits: 0, broke: 6 });
  assert.equal(c.maxHits, 6);
  assert.equal(c.bestTierName, "HYPER COMBO");
  assert.deepEqual(c.onResult("late"), { hits: 0 });               // nothing to break
  c.onResult("perfect"); c.onResult("perfect");
  assert.deepEqual(c.onResult("wrong"), { hits: 0 });              // 2 hits < breaker minimum
  assert.ok(BREAKER_MIN_HITS === 5);
});

test("combos: a long run of perfects climbs every tier up to ULTRA", () => {
  const c = new ComboTracker();
  const said = [];
  for (let i = 0; i < 25; i++) { const r = c.onResult("perfect"); if (r.announce) said.push(r.announce.text); }
  assert.deepEqual(said, TIERS.map(t => t[1]));
});

test("particles: bursts, physics, fade out, pool cap", () => {
  let seed = 1;
  const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const p = new ParticlePool(20);
  p.burst(100, 200, { count: 12, rand });
  assert.equal(p.size, 12);
  const y0 = p.items.map(s => s.y);
  p.step(50);
  assert.ok(p.items.some((s, i) => s.y < y0[i]));                  // upward burst
  p.burst(0, 0, { count: 15, rand });
  assert.equal(p.size, 20);                                         // capped, oldest recycled
  p.step(700);
  assert.equal(p.size, 0);                                          // all faded
});

test("rolling score: runs up quickly, never overshoots, lands exactly", () => {
  const n = new RollingNumber(0);
  n.set(1000);
  n.step(16);
  assert.ok(n.value > 0 && n.value < 1000);
  for (let i = 0; i < 200; i++) n.step(16);
  assert.equal(n.value, 1000);
  n.set(1003);
  n.step(16);                                                      // tiny gap: minimum speed kicks in
  assert.ok(n.value > 1000 && n.value <= 1003);
  for (let i = 0; i < 10; i++) n.step(16);
  assert.equal(n.shown, 1003);
  n.jump(5);
  assert.equal(n.shown, 5);
});
