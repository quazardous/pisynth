// Keyboard geometry + the visible key range (#2419 / #2418). Pure, unit-tested under Node.
//
// Everything is measured in WHITE-KEY units along the whole MIDI range: a white key is 1 wide,
// a black key 0.6, centred on the boundary between its two white neighbours. A view is a window
// {x0, span} over that axis, so the on-screen keyboard and the note highway's lanes share one
// mapping and stay aligned — even while the window slides by a fraction of a key.

import { isBlack } from "./theory.js";

export const PIANO_LOW = 21, PIANO_HIGH = 108;          // A0 .. C8
export const BLACK_W = 0.6;

// Left edge of note `n` in white-key units (white keys below it, minus half a black key).
export function keyX(n) {
  const oct = Math.floor(n / 12), pc = ((n % 12) + 12) % 12;
  const whitesBefore = oct * 7 + [0, 1, 1, 2, 2, 3, 4, 4, 5, 5, 6, 6][pc];
  return isBlack(n) ? whitesBefore - BLACK_W / 2 : whitesBefore;
}

export function keyRect(n) {
  const black = isBlack(n);
  return { n, black, x: keyX(n), w: black ? BLACK_W : 1 };
}

// The view showing low..high exactly (low/high widened to the nearest white keys).
export function rangeView(low, high) {
  if (isBlack(low)) low -= 1;
  if (isBlack(high)) high += 1;
  const x0 = keyX(low);
  return { x0, span: keyX(high) + 1 - x0 };
}

export const whiteCount = (low, high) => rangeView(low, high).span;

// Percent position/size of a rect inside a view (what CSS `left`/`width` and the canvas use).
export function toPct(rect, view) {
  return { left: ((rect.x - view.x0) / view.span) * 100, width: (rect.w / view.span) * 100 };
}

// Keys shown in the view, in MIDI order: white keys at least partly inside, black keys whose
// centre is inside (so a C..C range doesn't grow a clipped C# at its edge).
export function keysInView(view, low = PIANO_LOW, high = PIANO_HIGH) {
  const out = [], end = view.x0 + view.span;
  for (let n = low; n <= high; n++) {
    const r = keyRect(n), c = r.x + r.w / 2;
    if (r.black ? c > view.x0 && c < end : r.x + r.w > view.x0 && r.x < end) out.push(r);
  }
  return out;
}

const clampView = (x0, span) => {
  const lo = keyX(PIANO_LOW), hi = keyX(PIANO_HIGH) + 1;
  return Math.min(Math.max(x0, lo), Math.max(lo, hi - span));
};

// Pick how a song is shown on a screen `widthPx` wide.
//  - fits with white keys >= minWhitePx → "fixed" on the song's range, widened to whole octaves
//    (C..C) and to at least minSpan white keys, centred;
//  - otherwise → "follow": a window of comfortable keys that slides with the music.
export function planView(songLow, songHigh, widthPx, { minWhitePx = 18, comfortPx = 24, minSpan = 15 } = {}) {
  const maxWhites = Math.max(7, Math.floor(widthPx / minWhitePx));
  const low = songLow - (((songLow % 12) + 12) % 12);                    // down to a C
  const high = songHigh + ((12 - (((songHigh % 12) + 12) % 12)) % 12);   // up to a C
  const song = rangeView(low, high);
  if (song.span <= maxWhites) {
    const span = Math.min(maxWhites, Math.max(song.span, minSpan));
    return { mode: "fixed", x0: clampView(song.x0 - (span - song.span) / 2, span), span };
  }
  const span = Math.max(7, Math.min(maxWhites, Math.floor(widthPx / comfortPx)));
  const mid = (keyX(songLow) + keyX(songHigh) + 1) / 2;
  return { mode: "follow", x0: clampView(mid - span / 2, span), span };
}

// The "follow" window: keeps the notes being played in view, then as many of the coming notes
// as fit (earliest first), and only moves when something would fall outside. It glides towards
// its target instead of jumping.
export class FollowView {
  constructor({ x0, span, margin = 0.5, tauMs = 220 }) {
    this.x0 = x0; this.span = span; this.margin = margin; this.tauMs = tauMs;
    this.target = x0;
  }

  // active: notes sounding now (must stay visible); upcoming: notes due soon, sorted by start.
  aim(active, upcoming) {
    const room = this.span - 2 * this.margin;
    let lo = Infinity, hi = -Infinity;
    const take = n => {
      const r = keyRect(n), nlo = Math.min(lo, r.x), nhi = Math.max(hi, r.x + r.w);
      if (nhi - nlo > room && lo !== Infinity) return false;
      lo = nlo; hi = nhi; return true;
    };
    for (const n of active) take(n);                      // never lose a note being played
    for (const n of upcoming) if (!take(n)) break;        // then the next ones, while they fit
    if (lo === Infinity) return this.target;
    let t = this.target;
    if (lo < t + this.margin) t = lo - this.margin;
    if (hi > t + this.span - this.margin) t = hi + this.margin - this.span;
    this.target = clampView(t, this.span);
    return this.target;
  }

  step(dtMs) {
    const d = this.target - this.x0;
    this.x0 = Math.abs(d) < 0.01 ? this.target : this.x0 + d * (1 - Math.exp(-Math.max(0, dtMs) / this.tauMs));
    return { x0: this.x0, span: this.span };
  }

  jump(x0) { this.x0 = this.target = clampView(x0, this.span); }
}
