import test from "node:test";
import assert from "node:assert/strict";
import { encodePath, parentOf, baseName, displayName, folderLabel, childrenOf, crumbs, songInfo, InfoCache, nextSongEntry, searchLibrary } from "../../web/app/src/lib/library.js";
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
  assert.equal(folderLabel("starter/1-first-steps"), "1 · first steps");
  assert.equal(folderLabel("0-homer"), "0 · homer");
  assert.equal(folderLabel("Mes morceaux"), "Mes morceaux");
  assert.equal(folderLabel("2024"), "2024");
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

test("next song: the next file in the folder, then the first of the next folder (the next level)", () => {
  const e = (path, kind = "file") => ({ path, kind });
  const entries = [e("starter", "dir"), e("starter/0-homer", "dir"), e("starter/1-first-steps", "dir"), e("starter/2-empty", "dir"),
    e("starter/3-beginner", "dir"), e("starter/0-homer/2-b.mid"), e("starter/0-homer/10-c.mid"), e("starter/0-homer/1-a.mid"),
    e("starter/1-first-steps/x.mid"), e("starter/3-beginner/y.mid"), e("mine.mid")];
  assert.equal(nextSongEntry(entries, "starter/0-homer/1-a.mid").path, "starter/0-homer/2-b.mid");
  assert.equal(nextSongEntry(entries, "starter/0-homer/2-b.mid").path, "starter/0-homer/10-c.mid");      // numeric order
  assert.equal(nextSongEntry(entries, "starter/0-homer/10-c.mid").path, "starter/1-first-steps/x.mid");  // next level
  assert.equal(nextSongEntry(entries, "starter/1-first-steps/x.mid").path, "starter/3-beginner/y.mid");  // skips an empty one
  assert.equal(nextSongEntry(entries, "starter/3-beginner/y.mid"), null);
  assert.equal(nextSongEntry(entries, "mine.mid"), null);
  assert.equal(nextSongEntry(entries, "gone.mid"), null);
});

test("songs: a MIDI file and a score of the same name are one song; a score alone is a song (#2657)", async () => {
  const { songsOf, isScorePath, stemOf } = await import("../../web/app/src/lib/library.js");
  const f = (path, type) => ({ path, kind: "file", type });
  const songs = songsOf([f("a/Ode.mid"), f("a/Ode.musicxml"), f("a/Solo.mxl"), f("a/Just.mid")]);
  assert.deepEqual(songs.map(s => [s.path, s.score?.path ?? null]), [["a/Ode.mid", "a/Ode.musicxml"], ["a/Solo.mxl", "a/Solo.mxl"], ["a/Just.mid", null]]);
  assert.ok(isScorePath("x.XML") && isScorePath("x.mxl") && !isScorePath("x.mid"));
  assert.equal(stemOf("a/b.musicxml"), "a/b");
  assert.equal(displayName("a/0-homer/3-Au-clair.musicxml"), "3 Au clair");
});

test("the gallery's search finds library songs by name or folder, any word order, no accents (#2667)", () => {
  const f = (path, extra = {}) => ({ kind: "file", path, size: 1, ...extra });
  const entries = [{ kind: "dir", path: "starter" }, f("starter/0-homer/7-Ode-to-joy.mid"), f("starter/0-homer/7-Ode-to-joy.musicxml"),
                   f("starter/3-intermediate/Beethoven-Fur-Elise-WoO-59.mxl"), f("Mes morceaux/Für Élise.mid")];
  assert.deepEqual(searchLibrary(entries, "joy ode").map(e => e.path), ["starter/0-homer/7-Ode-to-joy.mid"]);   // paired: one song
  assert.ok(searchLibrary(entries, "joy ode")[0].score);
  assert.deepEqual(searchLibrary(entries, "fur eli").map(e => e.path), ["Mes morceaux/Für Élise.mid", "starter/3-intermediate/Beethoven-Fur-Elise-WoO-59.mxl"]);
  assert.deepEqual(searchLibrary(entries, "homer").length, 1);                                               // the folder counts
  assert.deepEqual(searchLibrary(entries, "  "), []);
  assert.deepEqual(searchLibrary(entries, "nothing here"), []);
});
