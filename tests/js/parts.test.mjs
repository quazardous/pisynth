// Hybrid mode's parts: from markers (our starter songs), else from bars; cleared parts remembered.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseMidi } from "../../web/app/src/lib/midifile.js";
import { songNotes } from "../../web/app/src/lib/highway.js";
import { songParts, partAt, partName, partState, PartBook } from "../../web/app/src/lib/parts.js";

const load = f => {
  const b = readFileSync(new URL(`../../library/midi/${f}`, import.meta.url));
  const song = parseMidi(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
  return { song, notes: songNotes(song.events, song.durationMs) };
};

test("parts: the starter songs' markers, named, back to back, covering every note", () => {
  const { song, notes } = load("0-homer/3-Au-clair-de-la-lune.mid");
  assert.equal(song.markers.length, 4);
  const parts = songParts(song, notes);
  assert.deepEqual(parts.map(p => p.label), ["Au clair de la lune", "Mon ami Pierrot", "Ma chandelle est morte", "Ouvre-moi ta porte"]);
  for (let i = 1; i < parts.length; i++) assert.equal(parts[i].a, parts[i - 1].b);
  assert.equal(parts.at(-1).b, song.durationMs);
  assert.equal(parts.reduce((s, p) => s + p.notes, 0), notes.length);
  assert.equal(parts[0].first, 0);
  assert.equal(parts[1].first, parts[0].last + 1);
  assert.equal(parts.at(-1).last, notes.length - 1);
  assert.equal(partAt(parts, parts[2].a + 10), 2);
  assert.equal(partAt(parts, -5), 0);
  assert.equal(partName("Part 3 · Ding, dang, dong"), "Ding, dang, dong");
  assert.equal(partName("Coda"), "Coda");
});

test("parts: any other file is cut every 4 bars (8 in a long song), tiny tails glued on", () => {
  const { song, notes } = load("2-beginner/Handel-Sonatina-Aylesford.mid");
  assert.equal(song.markers.length, 0);
  const parts = songParts(song, notes);
  assert.ok(parts.length >= 3, `${parts.length} parts`);
  assert.ok(parts.every(p => p.notes >= 3));
  assert.equal(parts.reduce((s, p) => s + p.notes, 0), notes.length);
  assert.equal(parts[0].label, "Part 1");
  const mk = (n, gap) => Array.from({ length: n }, (_, i) => ({ note: 60, start: i * gap, end: i * gap + 100 }));
  const short = songParts({ bpm: 120, durationMs: 8100, markers: [] }, mk(17, 500));   // 4 bars of 2 s, then one note
  assert.equal(short.length, 1);                                // the lonely note of part 2 joins part 1
  assert.equal(short[0].b, 8100);
  assert.equal(songParts({ bpm: 120, durationMs: 16100, markers: [] }, mk(33, 500)).length, 2);
  assert.deepEqual(songParts({ bpm: 120, durationMs: 0 }, []), []);
});

test("cleared parts are remembered per song and can be forgotten", () => {
  const m = new Map(), store = { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) };
  const book = new PartBook(store, "k");
  book.clear("a.mid", 2); book.clear("a.mid", 1);
  assert.equal(new PartBook(store, "k").cleared("a.mid"), 2);
  book.forget("a.mid");
  assert.equal(new PartBook(store, "k").cleared("a.mid"), 0);
});

test("a part's state: strikes left (a chord counts once), done when all judged, missed if one was", () => {
  const notes = [{ start: 0 }, { start: 500 }, { start: 510 }, { start: 1000 }, { start: 1500 }];   // 510: chord with 500
  const part = { first: 0, last: 3 };
  assert.deepEqual(partState(notes, [null, null, null, null, null], part), { remaining: 3, missed: false, done: false });
  assert.deepEqual(partState(notes, ["perfect", "good", null, null, null], part), { remaining: 2, missed: false, done: false });
  assert.deepEqual(partState(notes, ["perfect", "good", "late", "perfect", null], part), { remaining: 0, missed: false, done: true });
  assert.equal(partState(notes, ["perfect", "miss", "late", "early", null], part).missed, true);
});
