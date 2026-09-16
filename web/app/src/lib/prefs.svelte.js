// Preferences of this phone (#2418), shared by every screen and remembered in the browser. Set under the
// cog → Display. (The playing aids — fingers, ghost keys… — are per musician: lib/aids.svelte.js.)
//   notation: "en" (C D E) or "fr" (Do Ré Mi) — a French browser starts in French

const KEYS = { notation: "pisynth.notation", arcade: "pisynth.arcade", playMode: "pisynth.playMode", view: "pisynth.view",
  lastSong: "pisynth.lastSong", scoreFx: "pisynth.scoreFx", scoreNames: "pisynth.scoreNames", scoreZoom: "pisynth.scoreZoom" };
export const PLAY_MODES = ["normal", "hybrid", "infinite"];

function read(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function write(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private mode */ }
}

function initialNotation() {
  const saved = read(KEYS.notation);
  if (saved === "en" || saved === "fr") return saved;
  return (globalThis.navigator?.language || "").toLowerCase().startsWith("fr") ? "fr" : "en";
}

export const prefs = $state({ notation: initialNotation(), arcade: read(KEYS.arcade) !== "0",
  playMode: PLAY_MODES.includes(read(KEYS.playMode)) ? read(KEYS.playMode) : "hybrid",
  view: read(KEYS.view) === "game" ? "game" : "piano", scoreFx: read(KEYS.scoreFx) === "1" });

// The score's look (#2667): note names under the notes (on by default), and its size, -100 … +100 (% steps: half
// size … double size, 0 = as drawn).
export const clampZoom = z => (Number.isFinite(+z) ? Math.max(-100, Math.min(100, Math.round(+z))) : 0);
export const zoomFactor = z => 2 ** (clampZoom(z) / 100);
Object.assign(prefs, { scoreNames: read(KEYS.scoreNames) !== "0", scoreZoom: clampZoom(read(KEYS.scoreZoom) ?? 0) });
export function setScoreNames(on) {
  prefs.scoreNames = !!on;
  write(KEYS.scoreNames, prefs.scoreNames ? "1" : "0");
}
export function setScoreZoom(z) {
  prefs.scoreZoom = clampZoom(z);
  write(KEYS.scoreZoom, String(prefs.scoreZoom));
}

// scoreFx (#2667): Score mode plays calmly by default; on, it has the game's effects and points (and XP) too.
export function setScoreFx(on) {
  prefs.scoreFx = !!on;
  write(KEYS.scoreFx, prefs.scoreFx ? "1" : "0");
}

// view (#2657): "piano" (the default) shows the song's score, calm, like a music stand; "game" the falling
// notes with the arcade effects. A song without a score shows its falling notes either way.
export function setView(v) {
  prefs.view = v === "game" ? "game" : "piano";
  write(KEYS.view, prefs.view);
}

// The song open last time, opened again when the companion starts: {path, score} (library paths).
export function lastSong() {
  try { const s = JSON.parse(read(KEYS.lastSong) || "null"); return typeof s?.path === "string" ? s : null; } catch { return null; }
}
export function setLastSong(song) {
  if (song?.path) write(KEYS.lastSong, JSON.stringify({ path: song.path, score: song.scorePath ?? null, catalog: song.catalog ?? null }));
}

// playMode, how "I play" runs a song: normal (once) · hybrid (part by part, each unlocked by the one before) · infinite (loops)
export function setPlayMode(m) {
  prefs.playMode = PLAY_MODES.includes(m) ? m : "hybrid";
  write(KEYS.playMode, prefs.playMode);
}

// arcade: explosions, combos, announcer and their sounds in "I play" (#2434) — on by default
export function setArcade(on) {
  prefs.arcade = !!on;
  write(KEYS.arcade, prefs.arcade ? "1" : "0");
}

export function setNotation(value) {
  prefs.notation = value === "fr" ? "fr" : "en";
  write(KEYS.notation, prefs.notation);
}

