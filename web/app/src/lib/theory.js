// Note names and chord recognition (#659) — runs on the phone. Pure, unit-tested under Node.

export const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export function noteName(n) { return NAMES[((n % 12) + 12) % 12] + (Math.floor(n / 12) - 1); }

export function isBlack(n) { return [1, 3, 6, 8, 10].includes(((n % 12) + 12) % 12); }

const SHAPES = [
  [[0, 4, 7], ""], [[0, 3, 7], "m"], [[0, 3, 6], "dim"], [[0, 4, 8], "aug"],
  [[0, 5, 7], "sus4"], [[0, 2, 7], "sus2"],
  [[0, 4, 7, 10], "7"], [[0, 4, 7, 11], "maj7"], [[0, 3, 7, 10], "m7"], [[0, 3, 7, 11], "m(maj7)"],
  [[0, 3, 6, 10], "m7b5"], [[0, 3, 6, 9], "dim7"], [[0, 4, 7, 9], "6"], [[0, 3, 7, 9], "m6"],
  [[0, 2, 4, 7], "add9"],
];

// Best chord name for the sounding notes: tries each pitch class as root (lowest note first,
// so an inversion is named as a slash chord). Returns "" for no notes, the note name for one.
export function detectChord(notes) {
  if (!notes.length) return "";
  const sorted = [...notes].sort((a, b) => a - b);
  if (sorted.length === 1) return noteName(sorted[0]);
  const bass = ((sorted[0] % 12) + 12) % 12;
  const pcs = [...new Set(sorted.map(n => ((n % 12) + 12) % 12))];
  if (pcs.length === 1) return NAMES[bass];
  if (pcs.length === 2) {
    const iv = (pcs[1] - pcs[0] + 12) % 12;
    if (iv === 7 || iv === 5) return NAMES[iv === 7 ? pcs[0] : pcs[1]] + "5";
  }
  const roots = [bass, ...pcs.filter(p => p !== bass)];
  for (const root of roots) {
    const iv = pcs.map(p => (p - root + 12) % 12).sort((a, b) => a - b);
    for (const [shape, suffix] of SHAPES) {
      if (iv.length === shape.length && shape.every((v, i) => v === iv[i])) {
        return NAMES[root] + suffix + (root === bass ? "" : "/" + NAMES[bass]);
      }
    }
  }
  return "";
}
