// XP and levels (#2436), kept on the phone. A run earns XP for the notes you got right times how hard
// the song is at your tempo; songs easy for your level, and the same song again the same day, earn less
// and less (logarithmically). Pure apart from the injected storage; tested under Node.

export const NOTE_XP = { perfect: 1, good: 0.7, early: 0.3, late: 0.3 };
const XP_SCALE = 2;
const MIN_NOTES = 5;           // fewer judged notes than this earn nothing (a stop right after Play)

// XP to go from `level` to the next one.
export const xpToNext = level => Math.round(100 * Math.pow(level, 1.5));

// The difficulty a player of `level` is expected to handle: 1 at level 1, ≈ 5 at level 10, ≈ 8.7 at level 30.
export const levelDifficulty = level => Math.round((1 + 9 * (1 - Math.exp(-(level - 1) / 15))) * 10) / 10;

// Total XP → {level, into (XP inside this level), need (XP for the next one)}.
export function levelOf(xp) {
  let level = 1, left = Math.max(0, xp);
  while (left >= xpToNext(level)) { left -= xpToNext(level); level++; }
  return { level, into: left, need: xpToNext(level) };
}

// One run → {xp, base, easy, repeat}. `counts` = the judge's counts, `play` = which XP-paying play of this
// song today (1 = the first), `diff` = the song's difficulty at the tempo played.
export function runXp(counts, diff, level, play = 1) {
  const judged = ["perfect", "good", "early", "late", "miss"].reduce((s, k) => s + (counts[k] || 0), 0);
  if (judged < MIN_NOTES) return { xp: 0, base: 0, easy: 1, repeat: 1 };
  const hits = Object.entries(NOTE_XP).reduce((s, [k, v]) => s + (counts[k] || 0) * v, 0);
  const base = hits * diff * XP_SCALE;
  const gap = levelDifficulty(level) - diff;
  const easy = gap > 0 ? 1 / (1 + Math.log(1 + gap)) : 1;
  const repeat = 1 / (1 + Math.log(Math.max(1, play)));
  return { xp: Math.max(0, Math.round(base * easy * repeat)), base: Math.round(base), easy, repeat };
}

const today = now => new Date(now).toISOString().slice(0, 10);

export class Progress {
  constructor(storage = globalThis.localStorage, key = "pisynth.progress", now = () => Date.now()) {
    this.storage = storage; this.key = key; this.now = now;
    let saved = null;
    try { saved = JSON.parse(storage?.getItem(key) || "null"); } catch { /* broken: start over */ }
    this.xp = Number(saved?.xp) || 0;
    this.day = saved?.day || "";
    this.plays = saved?.plays || {};                           // song → XP-paying plays today
  }

  get level() { return levelOf(this.xp); }

  // A run is over: add its XP. Returns {…runXp(), before, after, song play number, levelUp}.
  award(song, counts, diff) {
    const day = today(this.now());
    if (day !== this.day) { this.day = day; this.plays = {}; }
    const before = levelOf(this.xp), play = (this.plays[song] || 0) + 1;
    const run = runXp(counts, diff, before.level, play);
    if (run.xp > 0) {
      this.xp += run.xp;
      this.plays[song] = play;
      try { this.storage?.setItem(this.key, JSON.stringify({ xp: this.xp, day: this.day, plays: this.plays })); } catch { /* private mode */ }
    }
    const after = levelOf(this.xp);
    return { ...run, play, before, after, levelUp: after.level > before.level };
  }
}
