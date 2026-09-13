import test from "node:test";
import assert from "node:assert/strict";
import { RecordBook, songKey } from "../../web/app/src/lib/records.js";

const memory = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }; };

test("records keep each best independently, count plays, persist", () => {
  let t = 1000;
  const store = memory(), book = new RecordBook(store, "k", () => t);
  const first = book.submit("starter/0-homer/1-Do-Re-Mi.mid", { score: 500, accuracy: 70, maxHits: 4, tempo: 80 });
  assert.equal(first.newScore, true);
  assert.equal(first.previous, null);
  t = 2000;
  const second = book.submit("starter/0-homer/1-Do-Re-Mi.mid", { score: 400, accuracy: 85, maxHits: 9 });
  assert.equal(second.newScore, false);
  assert.equal(second.newAccuracy, true);
  assert.equal(second.newCombo, true);
  assert.deepEqual(second.record, { score: 500, tempo: 80, accuracy: 85, maxHits: 9, plays: 2, last: 2000, bestAt: 1000 });
  assert.deepEqual(new RecordBook(store, "k").get("starter/0-homer/1-Do-Re-Mi.mid").score, 500);   // persisted
  assert.equal(book.get("other.mid"), null);
  assert.equal(book.submit("", { score: 1 }), null);
  assert.equal(new RecordBook({ getItem: () => "{broken" }).get("x"), null);
});

test("song key: library path, else the name", () => {
  assert.equal(songKey({ path: "starter/2-beginner/a.mid", name: "A" }), "starter/2-beginner/a.mid");
  assert.equal(songKey({ name: "Sample: scale" }), "name:Sample: scale");
  assert.equal(songKey(null), "");
});
