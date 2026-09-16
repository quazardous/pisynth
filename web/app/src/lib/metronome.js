// The metronome, managed from the companion while one is connected (#2658). Pure, tested under Node:
// tempo presets and tap tempo, the beat grids the phone clicks on, and the settings each musician keeps.
//   by       — who plays the click: "pisynth" (through the synth, the phone is a remote) or "phone"
//   bpm, beats, vol — the musician's metronome, given back to pisynth when they pick up the phone
//   inPlayer — click along with the song in the player, at the song's tempo

export const TEMPO_PRESETS = [["Largo", 50], ["Adagio", 66], ["Andante", 92], ["Moderato", 114],
  ["Allegro", 138], ["Vivace", 166], ["Presto", 184]];          // same list as the pisynth screen
export const BPM = [40, 240], BEATS = [1, 8];
export const METRO_DEFAULTS = { by: "pisynth", bpm: 100, beats: 4, vol: 80, inPlayer: false };

const clampInt = (v, lo, hi, dflt) => (Number.isFinite(+v) ? Math.max(lo, Math.min(hi, Math.round(+v))) : dflt);
export const clampBpm = v => clampInt(v, BPM[0], BPM[1], METRO_DEFAULTS.bpm);
export const clampBeats = v => clampInt(v, BEATS[0], BEATS[1], METRO_DEFAULTS.beats);
export const clampVol = v => clampInt(v, 0, 100, METRO_DEFAULTS.vol);

// The marking nearest a BPM ("80" is still an Andante).
export function nearestPreset(bpm) {
  return TEMPO_PRESETS.reduce((best, p) => (Math.abs(p[1] - bpm) < Math.abs(best[1] - bpm) ? p : best));
}

// Tap tempo: the taps so far (ms) and a new one → {taps, bpm}. A pause of 2 s starts over; the last
// taps are averaged; bpm is null until there are two.
export function tapTempo(taps, now, { gapMs = 2000, keep = 6 } = {}) {
  const next = taps.length && now - taps[taps.length - 1] > gapMs ? [now] : [...taps, now].slice(-keep);
  if (next.length < 2) return { taps: next, bpm: null };
  const avg = (next[next.length - 1] - next[0]) / (next.length - 1);
  return { taps: next, bpm: clampBpm(60000 / avg) };
}

// A steady grid: beat k at anchor + k·beatMs, numbered 1..beats from `first` (the beat number at k = 0).
// The first beat strictly after `after` → {at, n}.
export function gridBeat({ anchor, beatMs, beats, first = 1 }, after) {
  const k = Math.max(0, Math.floor((after - anchor) / beatMs + 1e-6) + 1);
  return { at: anchor + k * beatMs, n: ((first - 1 + k) % beats) + 1 };
}

// The song's grid, for the player: beats fall on song time k·beatMs (bar lines every `beatsPerBar`),
// `toSong`/`toLocal` convert between phone and song time. Only beats in [fromMs, toMs] click; null past it.
export function songBeat({ beatMs, beatsPerBar, fromMs, toMs, toSong, toLocal }, after) {
  let k = Math.floor(toSong(after) / beatMs + 1e-3) + 1;
  k = Math.max(k, Math.ceil(fromMs / beatMs - 1e-3));
  const songAt = k * beatMs;
  if (songAt > toMs) return null;
  return { at: toLocal(songAt), n: (((k % beatsPerBar) + beatsPerBar) % beatsPerBar) + 1 };
}

export function loadMetro(storage, key) {
  let saved = null;
  try { saved = JSON.parse(storage?.getItem(key) || "null"); } catch { /* broken: defaults */ }
  const m = { ...METRO_DEFAULTS };
  if (saved && typeof saved === "object") {
    if (saved.by === "phone" || saved.by === "pisynth") m.by = saved.by;
    if (saved.bpm !== undefined) m.bpm = clampBpm(saved.bpm);
    if (saved.beats !== undefined) m.beats = clampBeats(saved.beats);
    if (saved.vol !== undefined) m.vol = clampVol(saved.vol);
    m.inPlayer = saved.inPlayer === true;
  }
  return m;
}

export function saveMetro(m, storage, key) {
  const { by, bpm, beats, vol, inPlayer } = m;
  try { storage?.setItem(key, JSON.stringify({ by, bpm, beats, vol, inPlayer })); } catch { /* private mode */ }
}
