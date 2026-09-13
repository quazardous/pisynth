// Infinite mode: the song starts over by itself, lap after lap, with a score of its own that goes up
// with the notes you hit and down with the ones you miss or the wrong keys. Separate from the run's
// score, records and XP. The best per song is kept on the phone. Pure apart from the injected storage.

import { WRONG_PENALTY } from "./judge.js";

export const MISS_PENALTY = 40;                                // a missed note, × the tempo like the points

export class EndlessScore {
  constructor(storage = globalThis.localStorage, key = "pisynth.endless") {
    this.storage = storage; this.key = key;
    try { this.bests = JSON.parse(storage?.getItem(key) || "{}") || {}; } catch { this.bests = {}; }
    this.reset();
  }

  reset() { this.score = 0; this.laps = 0; this.peak = 0; }

  // A judged note: `gained` = the points the judge just gave (hits); misses and wrong keys cost.
  apply(kind, gained = 0, tempo = 1) {
    const delta = kind === "wrong" ? -WRONG_PENALTY : kind === "miss" ? -Math.round(MISS_PENALTY * tempo) : gained;
    this.score = Math.max(0, this.score + delta);
    this.peak = Math.max(this.peak, this.score);
    return delta;
  }

  best(song) { return this.bests[song] || 0; }

  // Keep the highest score this song reached (peak, not where it ended). Returns true on a new best.
  save(song) {
    if (!song || this.peak <= this.best(song)) return false;
    this.bests[song] = this.peak;
    try { this.storage?.setItem(this.key, JSON.stringify(this.bests)); } catch { /* private mode */ }
    return true;
  }
}
