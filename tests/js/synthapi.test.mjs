import test from "node:test";
import assert from "node:assert/strict";
import { SynthApi, throttle } from "../../web/app/src/lib/synthapi.js";

test("requests are matched to replies by id; pushes and unknown replies surface the state", async () => {
  const sent = [];
  const api = new SynthApi(m => { sent.push(m); return true; });
  const p = api.set("gain", 3);
  assert.deepEqual(sent[0], { t: "synth", op: "set", req: 1, key: "gain", value: 3 });
  assert.deepEqual(api.onMessage({ t: "synth", state: { gain: 2 } }), { gain: 2 });   // a watch push
  assert.deepEqual(api.onMessage({ t: "synth", req: 1, ok: true, state: { gain: 3 } }), { gain: 3 });
  assert.equal((await p).ok, true);
  assert.equal(api.onMessage({ t: "demo" }), null);
  const offline = new SynthApi(() => false);
  assert.equal((await offline.get()).error, "not connected");
});

test("throttle: first call at once, then the latest value at most every ms", () => {
  let t = 0;
  const calls = [], timers = [];
  const f = throttle(v => calls.push(v), 100, { now: () => t, setT: (fn, ms) => timers.push([t + ms, fn]) });
  f(1); f(2); f(3);
  assert.deepEqual(calls, [1]);
  t = 100; timers.shift()[1]();
  assert.deepEqual(calls, [1, 3]);                 // trailing call with the latest args
  t = 250; f(4);
  assert.deepEqual(calls, [1, 3, 4]);
});
