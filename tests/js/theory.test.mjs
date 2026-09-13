import test from "node:test";
import assert from "node:assert/strict";
import { detectChord, noteName, pitchName, isBlack } from "../../web/app/src/lib/theory.js";

test("note names", () => {
  assert.equal(noteName(60), "C4");
  assert.equal(noteName(21), "A0");
  assert.equal(noteName(61), "C#4");
  assert.ok(isBlack(61) && !isBlack(60));
});

test("French notation: Do Ré Mi, middle C = Do3", () => {
  assert.equal(noteName(60, "fr"), "Do3");
  assert.equal(noteName(62, "fr"), "Ré3");
  assert.equal(noteName(69, "fr"), "La3");                 // A4 = 440 Hz = La3 in France
  assert.equal(noteName(21, "fr"), "La-1");
  assert.equal(pitchName(66, "fr"), "Fa#");
  assert.equal(pitchName(66), "F#");
  assert.equal(detectChord([57, 60, 64], "fr"), "Lam");
  assert.equal(detectChord([64, 67, 72], "fr"), "Do/Mi");
  assert.equal(detectChord([55, 59, 62, 65], "fr"), "Sol7");
  assert.equal(detectChord([60], "fr"), "Do3");
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
