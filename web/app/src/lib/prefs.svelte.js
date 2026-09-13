// Display preferences of this phone (#2418), shared by every screen and remembered in the browser.
// notation: "en" (C D E) or "fr" (Do Ré Mi) — a French browser starts in French.

const KEY = "pisynth.notation";

function initial() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "en" || saved === "fr") return saved;
  } catch { /* private mode */ }
  return (globalThis.navigator?.language || "").toLowerCase().startsWith("fr") ? "fr" : "en";
}

export const prefs = $state({ notation: initial() });

export function setNotation(value) {
  prefs.notation = value === "fr" ? "fr" : "en";
  try { localStorage.setItem(KEY, prefs.notation); } catch { /* private mode */ }
}
