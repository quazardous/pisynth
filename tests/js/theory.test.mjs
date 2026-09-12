import test from "node:test";
import assert from "node:assert/strict";
import { detectChord, noteName, isBlack } from "../../web/app/src/lib/theory.js";

test("note names", () => {
  assert.equal(noteName(60), "C4");
  assert.equal(noteName(21), "A0");
  assert.equal(noteName(61), "C#4");
  assert.ok(isBlack(61) && !isBlack(60));
});

test("chords, inversions as slash chords, power chords", () => {
  assert.equal(detectChord([]), "");
  assert.equal(detectChord([60]), "C4");
  assert.equal(detectChord([60, 64, 67]), "C");
  assert.equal(detectChord([57, 60, 64]), "Am");
  assert.equal(detectChord([64, 67, 72]), "C/E");
  assert.equal(detectChord([55, 59, 62, 65]), "G7");
  assert.equal(detectChord([60, 64, 67, 71]), "Cmaj7");
  assert.equal(detectChord([48, 55]), "C5");
  assert.equal(detectChord([60, 72]), "C");
  assert.equal(detectChord([60, 61, 62]), "");
});
