// Play-along judge (#2418): matches the keys you press against the song's notes. Pure,
// unit-tested under Node. Times are song ms.
//
// The timing windows are a share of the beat, so they follow the song's tempo and the tempo slider: a
// slow song, or the same song at 50 %, gives more time. Each is kept between a floor (a press can't
// be judged tighter than hands and Wi-Fi allow) and a ceiling (a window never swallows the next note),
// both in real ms.

export const WINDOWS = {                                      // ± share of a beat, bounded in real ms
  perfect: { beat: 0.14, min: 100, max: 190 },
  good: { beat: 0.3, min: 200, max: 400 },
  ok: { beat: 0.5, min: 320, max: 650 },
};
export const POINTS = { perfect: 100, good: 70, early: 30, late: 30 };
export const WRONG_PENALTY = 25;                              // a wrong key costs points (never below 0)

export class Judge {
  // tempo: 1 = as written · beatMs: song ms per beat (60000 / bpm)
  constructor(notes, { tempo = 1, beatMs = 500, windows = WINDOWS } = {}) {
    this.notes = notes;                  // songNotes() output, sorted by start
    this.windows = windows;
    this.beatMs = beatMs;
    this.setTempo(tempo);
    this.reset(0);
  }

  setTempo(tempo) { this.tempo = tempo; }

  // ± window in real ms at the current tempo (what the player feels).
  realWindow(kind) {
    const w = this.windows[kind];
    return Math.min(w.max, Math.max(w.min, (w.beat * this.beatMs) / this.tempo));
  }

  // Forget everything from `fromMs` on (start, seek, loop). Notes before it are out of play.
  reset(fromMs = 0) {
    this.result = new Array(this.notes.length).fill(null);   // per note: kind or null
    this.from = fromMs;
    this.cursor = 0;                                          // notes before it are all judged
    while (this.cursor < this.notes.length && this.notes[this.cursor].start < fromMs) this.result[this.cursor++] = "skip";
    this.counts = { perfect: 0, good: 0, early: 0, late: 0, miss: 0, wrong: 0 };
    this.score = 0; this.streak = 0; this.bestStreak = 0;
  }

  win(kind) { return this.realWindow(kind) * this.tempo; }     // in song ms

  // A key pressed at song time `t`. Returns {kind, note, index?, delta?, penalty?}.
  press(note, t) {
    const ok = this.win("ok");
    let best = -1, bestAbs = Infinity;
    for (let i = this.cursor; i < this.notes.length; i++) {
      const n = this.notes[i];
      if (n.start > t + ok) break;
      if (this.result[i] || n.note !== note) continue;
      const d = Math.abs(t - n.start);
      if (d <= ok && d < bestAbs) { best = i; bestAbs = d; }
    }
    if (best < 0) {
      const penalty = Math.min(WRONG_PENALTY, this.score);
      this.counts.wrong++; this.streak = 0; this.score -= penalty;
      return { kind: "wrong", note, penalty };
    }
    const delta = t - this.notes[best].start;               // < 0 = early
    const kind = bestAbs <= this.win("perfect") ? "perfect" : bestAbs <= this.win("good") ? "good" : delta < 0 ? "early" : "late";
    this.result[best] = kind;
    this.counts[kind]++;
    this.streak = kind === "perfect" || kind === "good" ? this.streak + 1 : 0;
    this.bestStreak = Math.max(this.bestStreak, this.streak);
    this.score += Math.round(POINTS[kind] * (1 + Math.min(this.streak, 50) / 50) * this.tempo);   // faster pays more (#2436)
    return { kind, note, index: best, delta: delta / this.tempo };      // delta in real ms
  }

  // Song time moved to `t`: notes whose window has closed unplayed are misses. Returns them.
  advance(t) {
    const ok = this.win("ok"), missed = [];
    while (this.cursor < this.notes.length && this.notes[this.cursor].start + ok < t) {
      if (!this.result[this.cursor]) {
        this.result[this.cursor] = "miss";
        this.counts.miss++; this.streak = 0;
        missed.push(this.cursor);
      }
      this.cursor++;
    }
    return missed;
  }

  // Share of judged notes that were hit, weighted (perfect 1, good .7, early/late .3), in %.
  accuracy() {
    const c = this.counts, judged = c.perfect + c.good + c.early + c.late + c.miss;
    return judged ? Math.round(((c.perfect + 0.7 * c.good + 0.3 * (c.early + c.late)) / judged) * 100) : 0;
  }
}
