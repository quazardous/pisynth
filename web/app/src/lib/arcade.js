// Arcade layer for the note highway (#2434): combos with an announcer, particle bursts, a score
// counter that runs up. Pure (no DOM, no canvas), unit-tested under Node.

// Combo tiers, by combo power (a perfect counts 2, a good 1). Names are our own, in the spirit of
// fighting-game announcers.
export const TIERS = [
  [3, "TRIPLE COMBO", "#9fd3ff"], [5, "SUPER COMBO", "#5aa0ff"], [8, "HYPER COMBO", "#4fd18b"],
  [12, "BRUTAL COMBO", "#ffd23f"], [16, "MASTER COMBO", "#ff9f5a"], [20, "AWESOME COMBO", "#ff6bd6"],
  [30, "KILLER COMBO", "#ff5a5a"], [40, "ULTRA COMBO", "#ffffff"],
];
export const BREAKER_MIN_HITS = 5;

export class ComboTracker {
  constructor() { this.reset(); }

  reset() {
    this.hits = 0; this.power = 0; this.tier = -1;
    this.maxHits = 0; this.bestTier = -1;
  }

  // A judged press or miss. Returns {hits, announce?: {text, color, tier}, broke?: hits}.
  onResult(kind) {
    if (kind === "perfect" || kind === "good") {
      this.hits++;
      this.power += kind === "perfect" ? 2 : 1;
      this.maxHits = Math.max(this.maxHits, this.hits);
      let tier = this.tier;
      while (tier + 1 < TIERS.length && this.power >= TIERS[tier + 1][0]) tier++;
      const out = { hits: this.hits };
      if (tier > this.tier) {
        this.tier = tier;
        this.bestTier = Math.max(this.bestTier, tier);
        out.announce = { text: TIERS[tier][1], color: TIERS[tier][2], tier };
      }
      return out;
    }
    const broken = this.hits;
    this.hits = 0; this.power = 0; this.tier = -1;
    return broken >= BREAKER_MIN_HITS ? { hits: 0, broke: broken } : { hits: 0 };
  }

  get bestTierName() { return this.bestTier >= 0 ? TIERS[this.bestTier][1] : ""; }
}

// A fixed pool of particles: bursting sparks that fly, slow down, fall and fade.
export class ParticlePool {
  constructor(cap = 300) {
    this.cap = cap;
    this.items = [];
  }

  // `count` particles from (x, y): upward-biased burst of `speed` px/s, living `life` ms.
  burst(x, y, { count = 12, color = "#ffd23f", speed = 380, life = 600, spread = Math.PI, up = true, size = 3, rand = Math.random } = {}) {
    for (let i = 0; i < count; i++) {
      const a = (up ? -Math.PI / 2 : Math.PI / 2) + (rand() - 0.5) * spread * 2;
      const v = speed * (0.35 + rand() * 0.65);
      const p = { x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life, age: 0, color, size: size * (0.6 + rand() * 0.8) };
      if (this.items.length >= this.cap) this.items.shift();              // oldest spark makes room
      this.items.push(p);
    }
  }

  step(dtMs, { gravity = 900, drag = 2.2 } = {}) {
    const dt = Math.max(0, dtMs) / 1000, k = Math.exp(-drag * dt);
    for (const p of this.items) {
      p.vx *= k; p.vy = p.vy * k + gravity * dt;
      p.x += p.vx * dt; p.y += p.vy * dt;
      p.age += dtMs;
    }
    this.items = this.items.filter(p => p.age < p.life);
  }

  get size() { return this.items.length; }
}

// A number that runs up to its target like an arcade score counter: fast when far, never slow.
export class RollingNumber {
  constructor(value = 0, { tauMs = 180, minPerSec = 60 } = {}) {
    this.value = value; this.target = value; this.tauMs = tauMs; this.minPerSec = minPerSec;
  }

  set(target) { this.target = target; }
  jump(value) { this.value = this.target = value; }

  step(dtMs) {
    const d = this.target - this.value;
    if (d === 0) return this.value;
    const eased = d * (1 - Math.exp(-Math.max(0, dtMs) / this.tauMs));
    const floor = Math.sign(d) * this.minPerSec * dtMs / 1000;
    const move = Math.abs(eased) > Math.abs(floor) ? eased : floor;
    this.value = Math.abs(move) >= Math.abs(d) ? this.target : this.value + move;
    return this.value;
  }

  get shown() { return Math.round(this.value); }
}
