// Comic-book splash bubbles (#2434): spiky bursts behind the combo announcer and an "OOPS!"
// on a wrong key. Our own drawing (no clip-art): a star-like polygon with irregular spikes, drawn
// in SVG by Comic.svelte. Pure and seeded, so a bubble keeps its shape while it animates; tested under Node.

// Small deterministic PRNG (mulberry32): the same seed gives the same bubble.
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// A burst outline in a w×h box centred on (w/2, h/2): `spikes` points alternating between the outer
// ellipse (jittered by `jag`) and an inner one at `inner` of its size. Returns an SVG path "M…Z".
export function burstPath(seed, { w = 200, h = 120, spikes = 14, inner = 0.68, jag = 0.22 } = {}) {
  const r = rng(seed), cx = w / 2, cy = h / 2, pts = [];
  const turn = r() * Math.PI;                               // no two bubbles point the same way
  for (let i = 0; i < spikes * 2; i++) {
    const a = turn + (i / (spikes * 2)) * Math.PI * 2 + (r() - 0.5) * (Math.PI / spikes) * 0.5;
    const k = i % 2 === 0 ? 1 - r() * jag : inner * (1 - r() * jag * 0.4);
    pts.push([cx + Math.cos(a) * (w / 2) * k, cy + Math.sin(a) * (h / 2) * k]);
  }
  return "M" + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join("L") + "Z";
}

// The fuzz of a splash under a combo announcer, in the tier's colour: size, offset (% of the bubble), tilt, spikes.
export function comboSplash(seed, { color = "#ffd23f", breaker = false } = {}) {
  const r = rng(seed);
  return {
    seed,
    color: breaker ? "#ff3b3b" : color,
    scale: 0.85 + r() * 0.45,                              // × the base size
    dx: (r() - 0.5) * 30,
    dy: (r() - 0.5) * 30,
    tilt: (r() - 0.5) * 30,                                // degrees
    spikes: breaker ? 22 : 11 + Math.floor(r() * 8),
  };
}

// A new level (#2436): the big one, golden, the level under the words.
export const levelUpSplash = (seed, level) =>
  ({ seed, word: "LEVEL UP!", caption: `Lv ${level}`, color: "#ffd23f", scale: 1, dx: 0, dy: 0, tilt: -5 - rng(seed)() * 6, spikes: 18 });

// Hybrid mode: the next part is open.
export const unlockSplash = (seed, part) =>
  ({ seed, word: "UNLOCKED!", caption: `Part ${part}`, color: "#4fd18b", scale: 1, dx: 0, dy: 0, tilt: 4 + rng(seed)() * 6, spikes: 16 });

// A wrong key: "OOPS!" in a smaller, softer bubble, with the points it cost.
export const oopsSplash = (seed, penalty) => {
  const r = rng(seed);
  return { seed, word: "OOPS!", caption: penalty ? `−${penalty}` : "", color: "#a86bff", scale: 0.9 + r() * 0.2, dx: 0, dy: 0, tilt: (r() - 0.5) * 24, spikes: 9 };
};
