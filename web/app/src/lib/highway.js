// Note highway (#2418): song notes, what is on screen, and where. Pure, unit-tested under Node.
// Times are song milliseconds "as written" (tempo scaling is the player's business).

// Timed MIDI events → notes {note, start, end, vel, ch, track}, sorted by start then pitch.
// A note-on is closed by the next note-off of the same pitch and channel (first in, first out);
// one never closed ends at `durationMs`.
export function songNotes(events, durationMs = Infinity) {
  const open = new Map(), notes = [];
  for (const e of events) {
    const kind = e.status & 0xf0, ch = e.status & 0x0f, key = ch * 128 + e.d1;
    if (kind === 0x90 && e.d2 > 0) {
      const n = { note: e.d1, start: e.ms, end: null, vel: e.d2, ch, track: e.track ?? 0 };
      notes.push(n);
      if (!open.has(key)) open.set(key, []);
      open.get(key).push(n);
    } else if (kind === 0x80 || kind === 0x90) {
      const q = open.get(key);
      if (q?.length) q.shift().end = e.ms;
    }
  }
  const last = events.length ? events[events.length - 1].ms : 0;
  for (const n of notes) if (n.end === null) n.end = Math.max(n.start + 1, Number.isFinite(durationMs) ? durationMs : last);
  return notes.sort((a, b) => a.start - b.start || a.note - b.note);
}

export function noteRange(notes) {
  if (!notes.length) return { low: 60, high: 72 };
  let low = 127, high = 0;
  for (const n of notes) { low = Math.min(low, n.note); high = Math.max(high, n.note); }
  return { low, high };
}

// Tracks that carry notes, busiest first — with two, the usual piano file is right hand / left hand.
export function noteTracks(notes) {
  const count = new Map();
  for (const n of notes) count.set(n.track, (count.get(n.track) || 0) + 1);
  return [...count.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t);
}

// Index of the first note starting at or after `t` (binary search).
export function firstStartingAt(notes, t) {
  let lo = 0, hi = notes.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (notes[mid].start < t) lo = mid + 1; else hi = mid; }
  return lo;
}

// Notes overlapping [t - pastMs, t + aheadMs]. `maxLen` (longest note) bounds the backward scan.
export function visibleNotes(notes, t, aheadMs, pastMs = 0, maxLen = longestNote(notes)) {
  const out = [];
  for (let i = firstStartingAt(notes, t - pastMs - maxLen); i < notes.length; i++) {
    const n = notes[i];
    if (n.start > t + aheadMs) break;
    if (n.end >= t - pastMs) out.push(n);
  }
  return out;
}

export function longestNote(notes) {
  let m = 0;
  for (const n of notes) m = Math.max(m, n.end - n.start);
  return m;
}

// Vertical position (px from the top) of song time `ms` when the song is at `t`: the hit line is
// at `hitY`, the future is above it, `pxPerMs` fixes the fall speed.
export const timeToY = (ms, t, hitY, pxPerMs) => hitY - (ms - t) * pxPerMs;
