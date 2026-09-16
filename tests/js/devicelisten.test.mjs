// Listen on this device (#2670): pisynth's look-ahead batches turned into the browser piano's notes.
import test from "node:test";
import assert from "node:assert/strict";
import { batchNotes, LEAD_MS } from "../../web/app/src/lib/devicelisten.js";
import { DemoSender } from "../../web/app/src/lib/demo.js";

test("a batch becomes timed notes: note-on, note-off, velocity-0 note-on as off, other events skipped", () => {
  assert.deepEqual(batchNotes([[0, 0x90, 60, 90], [250.5, 0x80, 60, 0], [300, 0x90, 64, 0], [310, 0xb0, 64, 127]], 1000),
    [{ at: 1000, on: true, note: 60, velocity: 90 }, { at: 1250.5, on: false, note: 60, velocity: 0 }, { at: 1300, on: false, note: 64, velocity: 0 }]);
  assert.deepEqual(batchNotes(undefined, 0), []);
  assert.equal(LEAD_MS, 150);
});

test("the sender's batches at a tempo land at the right times on the device", () => {
  let t = 0;
  const sent = [];
  const events = [{ ms: 0, status: 0x90, d1: 60, d2: 80 }, { ms: 500, status: 0x80, d1: 60, d2: 0 }, { ms: 1000, status: 0x90, d1: 62, d2: 80 }];
  const s = new DemoSender({ events, send: m => sent.push(m), now: () => t, lookaheadMs: 2000 });
  s.start(0, 2);                                                   // twice as fast
  assert.equal(sent[0].reset, true);
  assert.deepEqual(batchNotes(sent[0].ev, 0).map(n => [n.at, n.on, n.note]), [[0, true, 60], [250, false, 60], [500, true, 62]]);
});
