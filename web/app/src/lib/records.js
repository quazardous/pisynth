// Personal records per song, kept on the phone (localStorage): best score, best accuracy, longest combo,
// how many plays and when (#2434 follow-up). Pure apart from the injected storage; tested under Node.

export class RecordBook {
  constructor(storage = globalThis.localStorage, key = "pisynth.records", now = () => Date.now()) {
    this.storage = storage; this.key = key; this.now = now;
    try { this.map = JSON.parse(storage?.getItem(key) || "{}") || {}; } catch { this.map = {}; }
  }

  get(song) { return this.map[song] || null; }

  // A run played to the end (tempo in %, kept with the best score). Returns {record, newScore, newAccuracy, newCombo, previous}.
  submit(song, { score = 0, accuracy = 0, maxHits = 0, tempo = 100 } = {}) {
    if (!song) return null;
    const previous = this.map[song] || null;
    const newScore = !previous || score > previous.score;
    const newAccuracy = !previous || accuracy > previous.accuracy;
    const newCombo = !previous || maxHits > previous.maxHits;
    const record = {
      score: newScore ? score : previous.score,
      tempo: newScore ? tempo : previous.tempo,
      accuracy: newAccuracy ? accuracy : previous.accuracy,
      maxHits: newCombo ? maxHits : previous.maxHits,
      plays: (previous?.plays || 0) + 1,
      last: this.now(),
      bestAt: newScore ? this.now() : previous.bestAt,
    };
    this.map[song] = record;
    try { this.storage?.setItem(this.key, JSON.stringify(this.map)); } catch { /* full or private mode */ }
    return { record, newScore: newScore && score > 0, newAccuracy, newCombo, previous };
  }
}

// The key a song is filed under: its library path, else its name (the built-in sample).
export const songKey = song => song?.path || (song?.name ? `name:${song.name}` : "");
