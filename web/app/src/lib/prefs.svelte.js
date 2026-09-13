// Display preferences of this phone (#2418, #2429), shared by every screen and remembered in the
// browser. Set under the cog → Display.
//   notation: "en" (C D E) or "fr" (Do Ré Mi) — a French browser starts in French
//   ghost:    ghost keys in "I play" (the perfect timing next to your playing) — on by default

const KEYS = { notation: "pisynth.notation", ghost: "pisynth.ghost", arcade: "pisynth.arcade", fingers: "pisynth.fingers" };

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

export const prefs = $state({ notation: initialNotation(), ghost: read(KEYS.ghost) !== "0", arcade: read(KEYS.arcade) !== "0",
  fingers: read(KEYS.fingers) !== "0" });

// fingers: the suggested finger on the falling notes and the keyboard (#2431) — on by default
export function setFingers(on) {
  prefs.fingers = !!on;
  write(KEYS.fingers, prefs.fingers ? "1" : "0");
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

export function setGhost(on) {
  prefs.ghost = !!on;
  write(KEYS.ghost, prefs.ghost ? "1" : "0");
}
