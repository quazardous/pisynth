// Playing aids per musician: all on by default, the phone's old settings as defaults, saved per musician.
import test from "node:test";
import assert from "node:assert/strict";
import { AIDS, loadAids, saveAids } from "../../web/app/src/lib/aids.js";

const memory = (init = {}) => { const m = new Map(Object.entries(init)); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }; };

test("aids: all on for a new musician, the phone's old ghost/fingers choices kept, saved per musician", () => {
  assert.deepEqual(loadAids(memory(), "pisynth.aids.m1"), { fingers: true, moves: true, ghost: true, shake: true });
  const old = memory({ "pisynth.ghost": "0" });
  assert.equal(loadAids(old, "pisynth.aids.m2").ghost, false);
  const store = memory();
  saveAids({ fingers: false, moves: true, ghost: true, shake: false }, store, "pisynth.aids.m1");
  assert.deepEqual(loadAids(store, "pisynth.aids.m1"), { fingers: false, moves: true, ghost: true, shake: false });
  assert.equal(loadAids(store, "pisynth.aids.m2").fingers, true);     // the other musicians untouched
  assert.equal(loadAids(memory({ k: "{broken" }), "k").shake, true);
  assert.deepEqual(AIDS, ["fingers", "moves", "ghost", "shake"]);
});
