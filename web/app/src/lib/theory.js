// Note names and chord recognition (#659) — runs on the phone. Pure, unit-tested under Node.
// Two notations (#2418): "en" (C D E…, middle C = C4) and "fr" (Do Ré Mi…, middle C = Do3, the
// French octave numbering).

export const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
export const NAMES_FR = ["Do", "Do#", "Ré", "Ré#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"];
export const NOTATIONS = ["en", "fr"];

const pc = n => ((n % 12) + 12) % 12;
const names = notation => (notation === "fr" ? NAMES_FR : NAMES);

// Pitch class name, no octave: "C#" / "Do#".
export function pitchName(n, notation = "en") { return names(notation)[pc(n)]; }

// With the octave: "C4" / "Do3" for middle C.
export function noteName(n, notation = "en") {
  return pitchName(n, notation) + (Math.floor(n / 12) - (notation === "fr" ? 2 : 1));
}

export function isBlack(n) { return [1, 3, 6, 8, 10].includes(pc(n)); }

const SHAPES = [
  [[0, 4, 7], ""], [[0, 3, 7], "m"], [[0, 3, 6], "dim"], [[0, 4, 8], "aug"],
  [[0, 5, 7], "sus4"], [[0, 2, 7], "sus2"],
  [[0, 4, 7, 10], "7"], [[0, 4, 7, 11], "maj7"], [[0, 3, 7, 10], "m7"], [[0, 3, 7, 11], "m(maj7)"],
  [[0, 3, 6, 10], "m7b5"], [[0, 3, 6, 9], "dim7"], [[0, 4, 7, 9], "6"], [[0, 3, 7, 9], "m6"],
  [[0, 2, 4, 7], "add9"],
];

// Best chord name for the sounding notes: tries each pitch class as root (lowest note first,
// so an inversion is named as a slash chord). Returns "" for no notes, the note name for one.
export function detectChord(notes, notation = "en") {
  if (!notes.length) return "";
  const N = names(notation);
  const sorted = [...notes].sort((a, b) => a - b);
  if (sorted.length === 1) return noteName(sorted[0], notation);
  const bass = pc(sorted[0]);
  const pcs = [...new Set(sorted.map(pc))];
  if (pcs.length === 1) return N[bass];
  if (pcs.length === 2) {
    const iv = (pcs[1] - pcs[0] + 12) % 12;
    if (iv === 7 || iv === 5) return N[iv === 7 ? pcs[0] : pcs[1]] + "5";
  }
  const roots = [bass, ...pcs.filter(p => p !== bass)];
  for (const root of roots) {
    const iv = pcs.map(p => (p - root + 12) % 12).sort((a, b) => a - b);
    for (const [shape, suffix] of SHAPES) {
      if (iv.length === shape.length && shape.every((v, i) => v === iv[i])) {
        return N[root] + suffix + (root === bass ? "" : "/" + N[bass]);
      }
    }
  }
  return "";
}
