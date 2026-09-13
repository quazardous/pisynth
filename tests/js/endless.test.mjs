// Infinite mode's own score: up with hits, down with misses and wrong keys, never below 0, best kept.
import test from "node:test";
import assert from "node:assert/strict";
import { EndlessScore, MISS_PENALTY } from "../../web/app/src/lib/endless.js";

test("endless score goes up and down, floors at 0, keeps the peak as the best", () => {
  const m = new Map(), store = { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) };
  const e = new EndlessScore(store, "k");
  e.apply("perfect", 102); e.apply("good", 72);
  assert.equal(e.score, 174);
  assert.equal(e.apply("miss", 0, 1), -MISS_PENALTY);
  assert.equal(e.apply("wrong"), -25);
  assert.equal(e.score, 109);
  e.apply("miss", 0, 0.5);                                     // slower tempo, smaller penalty
  assert.equal(e.score, 89);
  for (let i = 0; i < 10; i++) e.apply("miss");
  assert.equal(e.score, 0);
  assert.equal(e.peak, 174);
  assert.equal(e.save("a.mid"), true);
  assert.equal(new EndlessScore(store, "k").best("a.mid"), 174);
  e.reset();
  e.apply("perfect", 50);
  assert.equal(e.save("a.mid"), false);                        // below the best: kept as is
  assert.equal(e.save(""), false);
});
