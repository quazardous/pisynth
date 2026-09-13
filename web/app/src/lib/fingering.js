// Suggested piano fingering (#2431): MIDI files carry none, so it is computed — per hand, by dynamic
// programming over the fingers (1 = thumb … 5 = little finger) with ergonomic costs after Parncutt
// et al. (1997): comfortable / possible spans for each finger pair, thumb passing, black keys, weak
// 4th finger. Chords take fingers in pitch order, the subset whose spans fit best. Pure; tested under Node.
//
// Everything is worked out for the right hand; the left hand mirrors the pitches (a left hand going up
// is a right hand going down), keeping each key's colour.

import { keyX } from "./viewport.js";

const BLACK = new Set([1, 3, 6, 8, 10]);
export const isBlack = n => BLACK.has(((n % 12) + 12) % 12);

// Right hand, finger pair (i < j): semitones from finger i's key up to finger j's key.
// [MinPrac, MinComf, MinRel, MaxRel, MaxComf, MaxPrac] (Parncutt et al. 1997, table 1).
const SPANS = {
  "1-2": [-5, -3, 1, 5, 8, 10], "1-3": [-4, -2, 3, 7, 10, 12], "1-4": [-3, -1, 5, 9, 12, 14], "1-5": [-1, 1, 7, 10, 13, 15],
  "2-3": [1, 1, 1, 2, 3, 5], "2-4": [1, 1, 3, 4, 5, 7], "2-5": [2, 2, 5, 6, 8, 10],
  "3-4": [1, 1, 1, 2, 2, 4], "3-5": [1, 1, 3, 4, 5, 7], "4-5": [1, 1, 1, 2, 3, 5],
};
const IMPOSSIBLE = 40;
const RELAXED = 0.15;             // per semitone away from a resting hand's spacing (breaks the ties Parncutt leaves)
const CHORD_MS = 40;              // onsets closer than this form one chord
const REST_MS = 350;              // after a rest this long the hand may move freely (costs shrink)

// Cost of finger `a` on pitch `p` then finger `b` on pitch `q` (right-hand coordinates: q - p > 0 is up).
function spanCost(a, p, b, q) {
  if (a === b) return p === q ? 0 : 6 + Math.abs(q - p) * 0.5;   // same finger, another key: a jump
  const [i, j, d] = a < b ? [a, b, q - p] : [b, a, p - q];
  const [minP, minC, minR, maxR, maxC, maxP] = SPANS[`${i}-${j}`];
  const thumb = i === 1, k = thumb ? 1 : 2;
  let c = RELAXED * Math.abs(d - 2 * (j - i));                  // a resting hand: about a whole tone per finger
  if (d === 0) c += 1.5;                                        // the same key again with another finger
  if (d < minP || d > maxP) c += IMPOSSIBLE;
  if (d < minC) c += 2 * (minC - d);                            // stretch
  if (d > maxC) c += 2 * (d - maxC);
  if (d < minR) c += k * (minR - d);                            // small span
  if (d > maxR) c += k * (d - maxR);                            // large span
  return c;
}

// Moving from (a on p) to (b on q) — adds the sequential rules to the span.
function stepCost(a, p, b, q, realP, realQ) {
  let c = spanCost(a, p, b, q);
  if ((a === 3 && b === 4) || (a === 4 && b === 3)) c += 1;     // 3–4 in a row
  if (a === 3 && b === 4 && isBlack(realQ) && !isBlack(realP)) c += 1;
  if (b === 1 && isBlack(realQ) && !isBlack(realP)) c += 2;     // thumb onto a black key from a white one
  if (b === 5 && isBlack(realQ) && !isBlack(realP)) c += 2;     // little finger likewise
  const passing = (b === 1 && a > 1 && q > p) || (a === 1 && b > 1 && q < p);   // thumb under / finger over
  if (passing) {
    const [lo, hi] = q > p ? [realP, realQ] : [realQ, realP];
    const loFinger = q > p ? a : b;
    c += isBlack(lo) === isBlack(hi) ? 1 : !isBlack(lo) && loFinger !== 1 && isBlack(hi) ? 3 : 0;
  }
  return c;
}

// A finger on its own key, whatever comes around.
function fingerCost(f, real) {
  return (f === 4 ? 0.5 : 0) + (f === 1 && isBlack(real) ? 1 : 0);
}

// Every increasing choice of `k` fingers among 1..5.
function combos(k, from = 1) {
  if (k === 0) return [[]];
  const out = [];
  for (let f = from; f <= 6 - k; f++) for (const rest of combos(k - 1, f + 1)) out.push([f, ...rest]);
  return out;
}

// One hand's notes → fingers (Map note index → finger). `mirror` = left hand.
export function fingerHand(notes, mirror = false) {
  const sign = mirror ? -1 : 1;
  const events = [];                                            // chords: notes by onset, low → high (hand coordinates)
  for (const n of [...notes].sort((a, b) => a.start - b.start)) {
    const last = events[events.length - 1];
    if (last && n.start - last.start <= CHORD_MS) { last.notes.push(n); last.end = Math.max(last.end, n.end); }
    else events.push({ start: n.start, end: n.end, notes: [n] });
  }
  for (const e of events) {
    e.notes.sort((a, b) => sign * (a.note - b.note) || a.i - b.i);
    if (e.notes.length > 5) {                                   // more than five keys: the outer ones and three between
      const all = e.notes, m = all.length - 1;
      e.notes = [0, Math.round(m / 4), Math.round(m / 2), Math.round((3 * m) / 4), m].map(k => all[k]);
    }
    e.pos = e.notes.map(n => sign * n.note);
    e.states = combos(e.notes.length).map(fs => {
      let c = 0;
      for (let k = 0; k < fs.length; k++) {
        c += fingerCost(fs[k], e.notes[k].note);
        if (k) c += spanCost(fs[k - 1], e.pos[k - 1], fs[k], e.pos[k]);
      }
      return { fs, c };
    });
  }

  // Viterbi over the events: best total cost to reach each state, and where it came from.
  let prev = null;
  for (let ei = 0; ei < events.length; ei++) {
    const e = events[ei], p = events[ei - 1];
    for (const s of e.states) {
      if (!prev) { s.total = s.c; s.from = -1; continue; }
      const free = e.start - p.end >= REST_MS ? 0.2 : 1;
      let best = Infinity, from = 0;
      for (let si = 0; si < prev.length; si++) {
        const ps = prev[si];
        const lo = stepCost(ps.fs[0], p.pos[0], s.fs[0], e.pos[0], p.notes[0].note, e.notes[0].note);
        const single = ps.fs.length === 1 && s.fs.length === 1;
        const hi = single ? lo : stepCost(ps.fs.at(-1), p.pos.at(-1), s.fs.at(-1), e.pos.at(-1), p.notes.at(-1).note, e.notes.at(-1).note);
        const t = ps.total + ((lo + hi) / 2) * free;
        if (t < best) { best = t; from = si; }
      }
      s.total = best + s.c; s.from = from;
    }
    prev = e.states;
  }

  const out = new Map();
  out.cost = 0;                                                 // the whole hand's effort (#2436 difficulty)
  if (!events.length) return out;
  let si = prev.reduce((b, s, k) => (s.total < prev[b].total ? k : b), 0);
  out.cost = prev[si].total;
  for (let ei = events.length - 1; ei >= 0; ei--) {
    const s = events[ei].states[si];
    events[ei].notes.forEach((n, k) => out.set(n.i, s.fs[k]));
    si = s.from;
  }
  return out;
}

// Which hand plays each note: with two or more tracks, the track sounding highest is the right hand and
// the lowest the left (others go by pitch); one track within about an octave and a half is one hand;
// otherwise split at middle C.
export function splitHands(notes) {
  const byTrack = new Map();
  for (const n of notes) { if (!byTrack.has(n.track)) byTrack.set(n.track, []); byTrack.get(n.track).push(n.note); }
  const avg = a => a.reduce((s, x) => s + x, 0) / a.length;
  const tracks = [...byTrack.entries()].map(([t, ps]) => ({ t, avg: avg(ps), low: Math.min(...ps), high: Math.max(...ps) }))
    .sort((a, b) => b.avg - a.avg);
  const hand = new Map();
  if (tracks.length >= 2) {
    tracks.forEach((x, k) => hand.set(x.t, k === 0 ? "R" : k === tracks.length - 1 ? "L" : x.avg >= 60 ? "R" : "L"));
    return notes.map(n => hand.get(n.track));
  }
  const one = tracks[0];
  if (one && one.high - one.low <= 19) return notes.map(() => (one.avg >= 55 ? "R" : "L"));
  return notes.map(n => (n.note >= 60 ? "R" : "L"));
}

// Song notes (with `i`, their index) → [{finger, hand}] by index; `.cost` = both hands' total effort.
export function fingering(notes) {
  const hands = splitHands(notes), out = new Array(notes.length).fill(null);
  out.cost = 0;
  for (const h of ["R", "L"]) {
    const mine = notes.filter((_, k) => hands[k] === h), m = fingerHand(mine, h === "L");
    for (const [i, finger] of m) out[i] = { finger, hand: h };
    out.cost += m.cost;
  }
  return out;
}

// The fingers to show on the keyboard at song time `t`: for each key, the note held there or the next one
// starting before `t + aheadMs`, first come first shown. `maxLen` (longest note) bounds the backward scan.
// → Map note → {finger, hand, track}
export function keyFingers(notes, fingers, t, aheadMs, maxLen = Infinity) {
  const out = new Map();
  let i = 0, hi = notes.length;
  if (Number.isFinite(maxLen)) {                                // first note that can still be held at `t`
    while (i < hi) { const mid = (i + hi) >> 1; if (notes[mid].start < t - maxLen) i = mid + 1; else hi = mid; }
  }
  for (; i < notes.length; i++) {
    const n = notes[i];
    if (n.start > t + aheadMs) break;
    if (n.end < t) continue;
    const f = fingers[n.i];
    if (f && !out.has(n.note)) out.set(n.note, { ...f, track: n.track });
  }
  return out;
}

// Where the hand has to move (#2431): a hand's position is where its thumb sits, worked out from each
// key and its finger (a finger rests about one white key per finger from the thumb; the left hand mirrors).
// When the next notes need the thumb 1.5 white keys or more away, that's a new position.
// → by note index: null, or {dir: +1 up / −1 down, after: song ms of the hand's previous strike}.
export function handShifts(notes, fingers, threshold = 1.5) {
  const out = new Array(notes.length).fill(null);
  for (const hand of ["R", "L"]) {
    let anchor = null, lastStart = null, group = [], groupStart = -Infinity;
    const flush = () => {
      if (!group.length) return;
      const here = group.reduce((s, n) => s + keyX(n.note) + (hand === "R" ? 1 - fingers[n.i].finger : fingers[n.i].finger - 1), 0) / group.length;
      if (anchor !== null && Math.abs(here - anchor) >= threshold) {
        for (const n of group) out[n.i] = { dir: Math.sign(here - anchor), after: lastStart };
      }
      anchor = here; lastStart = group[0].start; group = [];
    };
    for (const n of notes) {                                    // sorted by start
      if (fingers[n.i]?.hand !== hand) continue;
      if (n.start - groupStart > 40) { flush(); groupStart = n.start; }
      group.push(n);
    }
    flush();
  }
  return out;
}

// At song time `t`: the moves to show — for each hand, its next move whose previous key has just been struck
// (so it appears right after that key). A move = where the hand is (`from`: its keys over the last `spanMs`
// before the move) and where it goes (`to`: its keys over the `spanMs` from the move), both with fingers.
// → [{hand, dir, from: Map note → {finger, hand, track}, to: Map note → …}]
export function upcomingShifts(notes, fingers, shifts, t, aheadMs, spanMs) {
  const moves = [], done = new Set();
  let i = 0, hi = notes.length;
  while (i < hi) { const mid = (i + hi) >> 1; if (notes[mid].start < t - 150) i = mid + 1; else hi = mid; }
  for (; i < notes.length && notes[i].start <= t + aheadMs; i++) {
    const n = notes[i], f = fingers[n.i], s = shifts[n.i];
    if (!f || done.has(f.hand)) continue;
    if (!s) {                                                  // this hand plays on in its position first
      if (n.start > t) done.add(f.hand);
      continue;
    }
    done.add(f.hand);
    if (s.after > t) continue;                                 // the key before the move isn't struck yet
    const pick = (lo, hi2) => {
      const out = new Map();
      for (const m of notes) {
        if (m.start > hi2) break;
        const g = fingers[m.i];
        if (m.start >= lo && g?.hand === f.hand && !out.has(m.note)) out.set(m.note, { ...g, track: m.track });
      }
      return out;
    };
    const to = pick(n.start, n.start + spanMs);
    const from = pick(s.after - spanMs, n.start - 1);
    for (const k of to.keys()) from.delete(k);                 // a key in both: it's where the hand goes
    moves.push({ hand: f.hand, dir: s.dir, from, to });
  }
  return moves;
}

// Stable text for a keyFingers() map, to skip re-rendering when nothing changed.
export const fingersKey = m => [...m].map(([n, f]) => `${n}:${f.finger}`).join(",");
