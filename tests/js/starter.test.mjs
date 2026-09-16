// The starter set shipped in library/midi (#2421, #2657): every song parses, has notes, and is usable by
// demo mode and the note highway. A song is a MIDI file, or a score on its own (the classical pieces from
// PDMX); a score beside a MIDI file of the same name is that file's score and matches it. From level 1 up
// a piece carries two hands on separate tracks; level 0 ("homer") is the right hand alone, on purpose.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { parseMidi } from "../../web/app/src/lib/midifile.js";
import { scoreSong } from "../../web/app/src/lib/musicxml.js";
import { readMxl } from "../../web/app/src/lib/mxl.js";
import { songNotes, noteTracks, noteRange } from "../../web/app/src/lib/highway.js";

const ROOT = new URL("../../library/midi/", import.meta.url).pathname;
const all = readdirSync(ROOT, { recursive: true }).sort();
const stem = f => f.replace(/\.[^./]+$/, "");
const midis = all.filter(f => /\.midi?$/i.test(f));
const scores = all.filter(f => /\.(musicxml|mxl)$/i.test(f));
const alone = scores.filter(f => !midis.some(m => stem(m) === stem(f)));
const LEVELS = ["0-homer", "1-first-steps", "2-beginner", "3-intermediate", "4-advanced"];

const bytes = f => { const b = readFileSync(join(ROOT, f)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
const loadMidi = f => parseMidi(bytes(f));
const loadScore = async f => scoreSong(f.endsWith(".mxl") ? await readMxl(bytes(f)) : readFileSync(join(ROOT, f), "utf8"));

test("the starter set is there, by numbered level", () => {
  assert.ok(midis.length + alone.length >= 28, `only ${midis.length + alone.length} songs`);
  for (const level of LEVELS) assert.ok([...midis, ...alone].some(f => f.startsWith(level + "/")), level);
  const folders = readdirSync(ROOT, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name).sort();
  assert.deepEqual(folders, LEVELS);
});

for (const f of [...midis, ...alone]) {
  const homer = f.startsWith("0-homer/");
  test(`starter: ${f} ${homer ? "is an easy right-hand piece" : "parses into two hands"}`, async () => {
    const song = /\.midi?$/i.test(f) ? loadMidi(f) : await loadScore(f);
    const notes = songNotes(song.events, song.durationMs);
    assert.ok(notes.length >= (homer ? 8 : 12), `${notes.length} notes`);
    assert.ok(song.durationMs > 8000 && song.durationMs < 15 * 60000, `${Math.round(song.durationMs)} ms`);
    assert.ok(song.bpm >= 40 && song.bpm <= 200, `${song.bpm} bpm`);
    if (homer) {
      const r = noteRange(notes);
      assert.equal(noteTracks(notes).length, 1);
      assert.ok(r.low >= 55 && r.high <= 69, `range ${r.low}-${r.high}`);          // stays within G3–A4
    } else {
      assert.ok(noteTracks(notes).length >= 2, `tracks with notes: ${noteTracks(notes)}`);
    }
  });
}

// (the generated .musicxml of levels 0–1 are checked note for note in musicxml.test.mjs)
for (const f of scores.filter(f => f.endsWith(".mxl") && !alone.includes(f))) {
  test(`starter: ${f} matches its MIDI file`, async () => {
    const s = await loadScore(f), m = loadMidi(midis.find(x => stem(x) === stem(f)));
    const key = n => `${Math.round(n.start / 10)}:${n.note}`;
    const a = songNotes(s.events, s.durationMs).map(key), z = new Set(songNotes(m.events, m.durationMs).map(key));
    assert.ok(a.filter(k => z.has(k)).length >= 0.98 * z.size, `${a.filter(k => z.has(k)).length} of ${z.size} notes in common`);
    assert.ok(existsSync(join(ROOT, stem(f) + ".mid")));
  });
}
