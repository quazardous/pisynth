import test from "node:test";
import assert from "node:assert/strict";
import { encodePath, parentOf, baseName, displayName, childrenOf, crumbs, songInfo, InfoCache } from "../../web/app/src/lib/library.js";
import { sampleSong } from "../../web/app/src/lib/midifile.js";

const entries = [
  { path: "starter", kind: "dir" },
  { path: "starter/beginner", kind: "dir" },
  { path: "starter/beginner/Bach-Minuet-10.mid", kind: "file", size: 10 },
  { path: "starter/beginner/Bach-Minuet-2.mid", kind: "file", size: 20 },
  { path: "Zeta.mid", kind: "file", size: 5 },
  { path: "mine", kind: "dir" },
];

test("paths: encode each segment, parent, base and display names", () => {
  assert.equal(encodePath("Mes morceaux/Für Elise.mid"), "Mes%20morceaux/F%C3%BCr%20Elise.mid");
  assert.equal(parentOf("a/b/c.mid"), "a/b");
  assert.equal(parentOf("c.mid"), "");
  assert.equal(baseName("a/b/c.mid"), "c.mid");
  assert.equal(displayName("starter/beginner/Bach-Minuet_in_G.MIDI"), "Bach Minuet in G");
});

test("children: folders first, natural name order, one level only", () => {
  const root = childrenOf(entries, "");
  assert.deepEqual(root.folders.map(e => e.path), ["mine", "starter"]);
  assert.deepEqual(root.files.map(e => e.path), ["Zeta.mid"]);
  assert.deepEqual(childrenOf(entries, "starter/beginner").files.map(e => baseName(e.path)), ["Bach-Minuet-2.mid", "Bach-Minuet-10.mid"]);
  assert.deepEqual(crumbs("starter/beginner"), [{ name: "starter", path: "starter" }, { name: "beginner", path: "starter/beginner" }]);
  assert.deepEqual(crumbs(""), []);
});

test("song info: duration, range and hands", () => {
  const info = songInfo(sampleSong());
  assert.equal(info.hands, 2);
  assert.ok(info.low < 50 && info.high === 72 && info.notes === 24 && info.durationMs > 5000);
});

test("info cache: keyed by path + size, persisted, bounded", () => {
  const store = new Map();
  const storage = { getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  const c = new InfoCache(storage, "k", 2);
  c.set(entries[2], { durationMs: 1 });
  assert.deepEqual(new InfoCache(storage, "k", 2).get(entries[2]), { durationMs: 1 });
  assert.equal(c.get({ ...entries[2], size: 11 }), null);          // file replaced → re-read
  c.set(entries[3], { durationMs: 2 });
  c.set(entries[4], { durationMs: 3 });
  assert.equal(c.get(entries[2]), null);                             // oldest dropped
  assert.deepEqual(c.get(entries[4]), { durationMs: 3 });
  assert.equal(new InfoCache({ getItem: () => "{bad json" }).get(entries[2]), null);
});
