// Playing aids, set per musician: a beginner keeps them all, someone more at ease turns some off.
// Pure apart from the injected storage; tested under Node.
//   fingers — the suggested finger on the falling notes and the keys (#2431)
//   moves   — hand moves: a green arrow and the next position in green
//   ghost   — ghost keys: the perfect timing on the keyboard (#2429)
//   shake   — a note shakes as it reaches the line

export const AIDS = ["fingers", "moves", "ghost", "shake"];
const LEGACY = { fingers: "pisynth.fingers", ghost: "pisynth.ghost" };   // when these were per phone

// A musician's aids (all on by default; the phone's old settings count as the defaults).
export function loadAids(storage, key) {
  const aids = {};
  let saved = null;
  try { saved = JSON.parse(storage?.getItem(key) || "null"); } catch { /* broken: defaults */ }
  for (const name of AIDS) {
    let legacy = null;
    try { legacy = LEGACY[name] ? storage?.getItem(LEGACY[name]) : null; } catch { /* private mode */ }
    aids[name] = typeof saved?.[name] === "boolean" ? saved[name] : legacy !== "0";
  }
  return aids;
}

export function saveAids(aids, storage, key) {
  try { storage?.setItem(key, JSON.stringify(Object.fromEntries(AIDS.map(n => [n, !!aids[n]])))); } catch { /* private mode */ }
}
