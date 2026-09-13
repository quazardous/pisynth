// The starter MIDI set shipped in library/midi (#2421): every file parses, has notes, and is usable by
// demo mode and the note highway. From level 1 up a piece carries two hands on separate tracks; level 0
// ("homer") is the right hand alone, on purpose.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parseMidi } from "../../web/app/src/lib/midifile.js";
import { songNotes, noteTracks, noteRange } from "../../web/app/src/lib/highway.js";

const ROOT = new URL("../../library/midi/", import.meta.url).pathname;
const files = readdirSync(ROOT, { recursive: true }).filter(f => /\.midi?$/i.test(f)).sort();
const LEVELS = ["0-homer", "1-first-steps", "2-beginner", "3-intermediate", "4-advanced"];

test("the starter set is there, by numbered level", () => {
  assert.ok(files.length >= 28, `only ${files.length} files`);
  for (const level of LEVELS) assert.ok(files.some(f => f.startsWith(level + "/")), level);
  const folders = readdirSync(ROOT, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name).sort();
  assert.deepEqual(folders, LEVELS);
});

for (const f of files) {
  const homer = f.startsWith("0-homer/");
  test(`starter: ${f} ${homer ? "is an easy right-hand piece" : "parses into two hands"}`, () => {
    const b = readFileSync(join(ROOT, f));
    const song = parseMidi(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
    const notes = songNotes(song.events, song.durationMs);
    assert.ok(notes.length >= (homer ? 8 : 12), `${notes.length} notes`);
    assert.ok(song.durationMs > 8000 && song.durationMs < 15 * 60000, `${Math.round(song.durationMs)} ms`);
    if (homer) {
      const r = noteRange(notes);
      assert.equal(noteTracks(notes).length, 1);
      assert.ok(r.low >= 55 && r.high <= 69, `range ${r.low}-${r.high}`);          // stays within G3–A4
    } else {
      assert.ok(noteTracks(notes).length >= 2, `tracks with notes: ${noteTracks(notes)}`);
    }
  });
}
