// Suggested fingering (#2431): the textbook patterns, both hands, black keys, chords, and the whole starter set.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { fingerHand, fingering, splitHands, keyFingers, fingersKey, isBlack } from "../../web/app/src/lib/fingering.js";
import { parseMidi } from "../../web/app/src/lib/midifile.js";
import { songNotes } from "../../web/app/src/lib/highway.js";

const N = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const pitch = s => 12 * (Number(s.at(-1)) + 1) + N[s[0]] + (s.includes("#") ? 1 : 0);
// "C4 D4 E4" → notes a beat apart (legato); "C4+E4+G4" = a chord
function line(text, { beat = 400, track = 0 } = {}) {
  const out = [];
  text.split(" ").forEach((tok, k) => tok.split("+").forEach(p => out.push({ note: pitch(p), start: k * beat, end: (k + 1) * beat - 10, track })));
  return out.map((n, i) => ({ ...n, i }));
}
const fingers = (text, mirror = false) => { const ns = line(text); const m = fingerHand(ns, mirror); return ns.map(n => m.get(n.i)).join(" "); };

test("fingering: the classic right-hand patterns", () => {
  assert.equal(fingers("C4 D4 E4 F4 G4 A4 B4 C5"), "1 2 3 1 2 3 4 5");
  assert.equal(fingers("C4 D4 E4 F4 G4"), "1 2 3 4 5");
  assert.equal(fingers("C4 E4 G4 C5"), "1 2 3 5");
  assert.equal(fingers("C4+E4+G4"), "1 3 5");
});

test("fingering: the left hand mirrors (C major scale going up)", () => {
  assert.equal(fingers("C3 D3 E3 F3 G3 A3 B3 C4", true), "5 4 3 2 1 3 2 1");
  assert.equal(fingers("C3+E3+G3", true), "5 3 1");
});

test("fingering: no thumb on the black keys of D major", () => {
  const ns = line("D4 E4 F#4 G4 A4 B4 C#5 D5"), m = fingerHand(ns);
  for (const n of ns) if (isBlack(n.note)) assert.notEqual(m.get(n.i), 1, `thumb on ${n.note}`);
});

test("fingering: a repeated note keeps a finger, leaps after a rest are free", () => {
  const f = fingers("E4 E4 E4 E4").split(" ");
  assert.equal(new Set(f).size, 1);
  const ns = [{ note: 60, start: 0, end: 300 }, { note: 84, start: 2000, end: 2300 }].map((n, i) => ({ ...n, i, track: 0 }));
  assert.equal(fingerHand(ns).size, 2);
});

test("fingering: hands by track, one small track is one hand, else split at middle C", () => {
  const two = [...line("C5 D5", { track: 1 }), ...line("C3 G2", { track: 2 })].map((n, i) => ({ ...n, i }));
  assert.deepEqual(splitHands(two), ["R", "R", "L", "L"]);
  assert.deepEqual(splitHands(line("C4 D4 E4 G4")), ["R", "R", "R", "R"]);
  assert.deepEqual(splitHands(line("C2 C5")), ["L", "R"]);
  const all = fingering(two);
  assert.ok(all.every(f => f && f.finger >= 1 && f.finger <= 5));
  assert.deepEqual(all.map(f => f.hand), ["R", "R", "L", "L"]);
});

test("fingering: big chords get the outer fingers, keys show the next finger", () => {
  const ns = line("C4+D4+E4+F4+G4+A4+B4");
  const m = fingerHand(ns);
  assert.equal(m.size, 5);
  const song = line("C4 D4 E4"), f = fingering(song);
  const k = keyFingers(song, f, 0, 450, 390);
  assert.deepEqual([...k.keys()], [60, 62]);
  assert.equal(k.get(60).finger, 1);
  assert.deepEqual([...keyFingers(song, f, 500, 100, 390).keys()], [62]);    // D held, E not yet due
  assert.equal(fingersKey(k), "60:1,62:2");
});

test("fingering: the children's songs get the fingering of the method books", () => {
  assert.equal(fingers("E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4"), "3 3 4 5 5 4 3 2 1 1 2 3");          // Ode to Joy
  assert.equal(fingers("C4 C4 G4 G4 A4 A4 G4"), "1 1 4 4 5 5 4");                                   // Twinkle twinkle
  assert.equal(fingers("E4 E4 E4 E4 E4 E4 E4 G4 C4 D4 E4"), "3 3 3 3 3 3 3 5 1 2 3");              // Jingle bells
});

test("fingering: every note of the starter library gets a finger, quickly", () => {
  const root = new URL("../../library/midi/", import.meta.url).pathname;
  for (const f of readdirSync(root, { recursive: true }).filter(f => /\.midi?$/i.test(f))) {
    const s = parseMidi(new Uint8Array(readFileSync(root + f)).buffer);
    const notes = songNotes(s.events, s.durationMs).map((n, i) => ({ ...n, i }));
    const t0 = performance.now(), fg = fingering(notes);
    assert.ok(performance.now() - t0 < 500, `${f}: too slow`);
    const bare = fg.filter(x => !x).length;
    assert.ok(bare <= notes.length * 0.01, `${f}: ${bare} notes without a finger`);            // only chords of 6+ keys in a hand
  }
});
