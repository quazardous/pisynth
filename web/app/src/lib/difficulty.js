// How hard a song is (#2436), from 1 (a few slow notes, one hand) to 10, as written — the tempo you
// choose weighs on the XP, not on the song's difficulty. Pure; tested under Node.
// The weights were fitted on the starter set (library/midi) against its levels: homer ≈ 1, first steps
// ≈ 2, then beginner < intermediate < advanced on average (those folders overlap, as editors' levels do).

import { fingering, splitHands, isBlack } from "./fingering.js";

const CHORD_MS = 40;          // onsets this close are one chord
const REST_CAP_MS = 1500;     // a long rest counts as this much: pauses don't make a song easier

// Song notes (with `i`) → what makes it hard. `fingers` (from fingering()) saves a second pass.
export function songFeatures(notes, fingers = fingering(notes)) {
  if (!notes.length) return { density: 0, chords: 0, hands: 0, black: 0, effort: 0 };
  let onsets = 0, inChords = 0, groupStart = -Infinity, groupSize = 0, active = 500, last = null;
  for (const n of notes) {                                    // sorted by start
    if (n.start - groupStart <= CHORD_MS) { groupSize++; continue; }
    if (groupSize > 1) inChords += groupSize;
    if (last !== null) active += Math.min(n.start - last, REST_CAP_MS);
    onsets++; groupStart = last = n.start; groupSize = 1;
  }
  if (groupSize > 1) inChords += groupSize;
  const hands = splitHands(notes), right = hands.filter(h => h === "R").length / notes.length;
  return {
    density: notes.length / (active / 1000),                  // notes per second of playing (a chord's notes all count)
    chords: inChords / notes.length,                          // share of notes struck with others
    hands: Math.min(right, 1 - right) * 2,                    // 0 = one hand … 1 = both hands equally
    black: notes.filter(n => isBlack(n.note)).length / notes.length,
    effort: (fingers.cost || 0) / notes.length,               // fingering cost per note (#2431)
  };
}

// Features → difficulty 1…10, one decimal.
export function difficulty(f) {
  const d = -0.7 + 1.7 * Math.log2(1 + f.density) + 0.1 * f.chords + 0.1 * f.hands + 2.1 * f.black
    + 0.95 * Math.log2(1 + f.effort);
  return Math.round(Math.min(10, Math.max(1, d)) * 10) / 10;
}

// Difficulty 1…10 → a gauge of `of` segments (1…10 → 1…5), the way games show it.
export const gaugeLevel = (d, of = 5) => Math.min(of, Math.max(1, Math.ceil((d / 10) * of - 1e-9)));
