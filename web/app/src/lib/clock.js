// Pi clock → phone clock (#2418). Each MIDI frame carries the Pi's monotonic ms (u32) taken when
// the key was pressed; the phone receives it a variable Wi-Fi delay later. The smallest
// (arrival − Pi time) seen recently is the clock offset plus the fastest trip, so a press is
// placed at the moment it was PLAYED, not when the network delivered it. Pure, tested under Node.

const WRAP = 2 ** 32;

export class ClockSync {
  constructor({ windowMs = 20000 } = {}) {
    this.windowMs = windowMs;
    this.samples = [];                   // [{local, diff}] oldest first
    this.lastPi = null;
    this.wraps = 0;
  }

  unwrap(piMs) {
    if (this.lastPi !== null && piMs < this.lastPi - WRAP / 2) this.wraps++;   // u32 rolled over
    this.lastPi = piMs;
    return piMs + this.wraps * WRAP;
  }

  // A frame stamped `piMs` arrived at phone time `localMs` (performance.now()).
  observe(piMs, localMs) {
    const diff = localMs - this.unwrap(piMs);
    this.samples.push({ local: localMs, diff });
    while (this.samples.length > 1 && this.samples[0].local < localMs - this.windowMs) this.samples.shift();
    if (this.samples.length > 512) this.samples.shift();
    return diff;
  }

  get offset() {
    if (!this.samples.length) return null;
    let m = Infinity;
    for (const s of this.samples) m = Math.min(m, s.diff);
    return m;
  }

  // Phone time at which the Pi stamped `piMs` (+ the fastest trip). Null before any sample.
  toLocal(piMs) {
    const o = this.offset;
    if (o === null) return null;
    let p = piMs + this.wraps * WRAP;
    if (this.lastPi !== null && piMs > this.lastPi + WRAP / 2) p -= WRAP;       // stamped just before a wrap
    return p + o;
  }

  // How late a press typically shows up beyond the fastest trip (median of the recent extra delay),
  // in ms — what the ghost keys wait so a perfect press and its ghost light up together (#2429).
  typicalLag(recent = 32) {
    const o = this.offset;
    if (o === null) return 0;
    const extra = this.samples.slice(-recent).map(s => s.diff - o).sort((a, b) => a - b);
    return extra[extra.length >> 1];
  }

  clear() { this.samples = []; this.lastPi = null; this.wraps = 0; }
}
