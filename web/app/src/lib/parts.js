// A song cut into parts, for the hybrid mode: a part must be played without a wrong key or a missed
// note to unlock the next one. Parts come from the file's markers (our starter songs mark their
// phrases and verses) or, for any other file, from its bars: 4 bars a part (8 in a long song). Pure
// apart from the injected storage; tested under Node.

const LONG_SONG_MS = 90_000;

// A marker's text → the part's name: "Part 2 · Mon ami Pierrot" → "Mon ami Pierrot".
export const partName = text => String(text || "").replace(/^\s*part\s*\d+\s*[·:.\-–—]?\s*/i, "").trim();

// song (parseMidi: markers, bpm, durationMs) + its notes → [{a, b, name, notes}] in song ms, back to back.
export function songParts(song, notes, { beatsPerBar = 4 } = {}) {
  const end = song.durationMs || 0;
  if (!notes.length || end <= 0) return [];
  const bar = (60000 / (song.bpm || 100)) * beatsPerBar;
  const marks = (song.markers || []).filter(m => m.ms < end).sort((x, y) => x.ms - y.ms);
  let starts;
  if (marks.length) starts = marks.map(m => ({ a: m.ms, name: partName(m.text) }));
  else {
    const len = bar * (end > LONG_SONG_MS ? 8 : 4);
    const origin = Math.floor(notes[0].start / bar) * bar;   // the bar line at or before the first note
    starts = [];
    for (let a = origin; a < end; a += len) starts.push({ a, name: "" });
  }
  const out = [];
  starts.forEach((s, i) => {
    const b = starts[i + 1]?.a ?? end;
    const count = notes.filter(n => n.start >= s.a && n.start < b).length;
    if (count === 0 || (count < 3 && out.length)) { if (out.length) out.at(-1).b = b; return; }   // glue a (nearly) empty part on
    out.push({ a: s.a, b, name: s.name, notes: count });
  });
  if (out.length) out[0].a = Math.min(out[0].a, notes[0].start);   // notes before the first marker belong to part 1
  return out.map((p, i) => ({ ...p, label: p.name || `Part ${i + 1}` }));
}

// The part holding song time `t` (the last one past the end).
export function partAt(parts, t) {
  for (let i = parts.length - 1; i >= 0; i--) if (t >= parts[i].a) return i;
  return 0;
}

// How many parts of each song a musician has cleared, remembered on the phone.
export class PartBook {
  constructor(storage = globalThis.localStorage, key = "pisynth.parts") {
    this.storage = storage; this.key = key;
    try { this.map = JSON.parse(storage?.getItem(key) || "{}") || {}; } catch { this.map = {}; }
  }

  cleared(song) { return this.map[song] || 0; }

  clear(song, count) {
    if (!song || count <= this.cleared(song)) return;
    this.map[song] = count;
    this.write();
  }

  forget(song) { delete this.map[song]; this.write(); }

  write() { try { this.storage?.setItem(this.key, JSON.stringify(this.map)); } catch { /* private mode */ } }
}
