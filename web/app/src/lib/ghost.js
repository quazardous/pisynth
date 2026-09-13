// Ghost keys (#2429): the perfect performance, shown next to yours. A key is ghost-pressed exactly
// while its note sounds in the score — no head start. Pure, tested under Node.

import { visibleNotes } from "./highway.js";

export const GHOST_MIN_MS = 45;          // a very short note still shows for a few frames

// Pitches ghost-pressed at song time `t`. `minMs` is in song ms (scale it by the tempo).
export function ghostKeys(notes, t, maxLen, minMs = GHOST_MIN_MS) {
  const on = new Set();
  for (const n of visibleNotes(notes, t, 0, minMs, maxLen)) {
    if (n.start <= t && t < Math.max(n.end, n.start + minMs)) on.add(n.note);
  }
  return on;
}

// Notes whose start the ghost crossed less than `pulseMs` ago: [{note, age}] (age in song ms), for
// the outline that pulses in their lane at the line.
export function ghostPulses(notes, t, maxLen, pulseMs) {
  const out = [];
  for (const n of visibleNotes(notes, t, 0, pulseMs, maxLen)) {
    const age = t - n.start;
    if (age >= 0 && age < pulseMs) out.push({ note: n.note, age });
  }
  return out;
}

export const sameSet = (a, b) => a.size === b.size && [...a].every(x => b.has(x));
