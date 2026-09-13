// Display preferences of this phone (#2418, #2429), shared by every screen and remembered in the
// browser. Set under the cog → Display.
//   notation: "en" (C D E) or "fr" (Do Ré Mi) — a French browser starts in French
//   ghost:    ghost keys in "I play" (the perfect timing next to your playing) — on by default

const KEYS = { notation: "pisynth.notation", ghost: "pisynth.ghost" };

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

export const prefs = $state({ notation: initialNotation(), ghost: read(KEYS.ghost) !== "0" });

export function setNotation(value) {
  prefs.notation = value === "fr" ? "fr" : "en";
  write(KEYS.notation, prefs.notation);
}

export function setGhost(on) {
  prefs.ghost = !!on;
  write(KEYS.ghost, prefs.ghost ? "1" : "0");
}
