// The starter MIDI set shipped in library/midi (#2421): every file parses, has notes, and is
// usable by both demo mode and the note highway — i.e. carries two hands on separate tracks.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { parseMidi } from "../../web/app/src/lib/midifile.js";
import { songNotes, noteTracks } from "../../web/app/src/lib/highway.js";

const ROOT = new URL("../../library/midi/", import.meta.url).pathname;
const files = readdirSync(ROOT, { recursive: true }).filter(f => /\.midi?$/i.test(f)).sort();

test("the starter set is there, by level", () => {
  assert.ok(files.length >= 21, `only ${files.length} files`);
  for (const level of ["1-first-steps", "2-beginner", "3-intermediate", "4-advanced"]) assert.ok(files.some(f => f.startsWith(level + "/")), level);
});

for (const f of files) {
  test(`starter: ${f} parses into two hands`, () => {
    const b = readFileSync(join(ROOT, f));
    const song = parseMidi(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
    const notes = songNotes(song.events, song.durationMs);
    assert.ok(notes.length >= 12, `${notes.length} notes`);
    assert.ok(song.durationMs > 8000 && song.durationMs < 15 * 60000, `${Math.round(song.durationMs)} ms`);
    assert.ok(noteTracks(notes).length >= 2, `tracks with notes: ${noteTracks(notes)}`);
  });
}
