// Arcade sound effects for the note highway (#2434), synthesised by the phone (Web Audio): a rising
// sting per combo tier, a glitchy "combo breaker" and a little "oops" on a wrong key. Short and quiet enough to sit over the piano.

import { audioContext } from "./click.js";

function voice(ac, { type = "sawtooth", freq, to = null, at, dur, peak, cutoff = 4000 }) {
  const osc = ac.createOscillator(), lp = ac.createBiquadFilter(), g = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, at);
  if (to) osc.frequency.exponentialRampToValueAtTime(to, at + dur * 0.8);
  lp.type = "lowpass";
  lp.frequency.setValueAtTime(cutoff, at);
  lp.frequency.exponentialRampToValueAtTime(Math.max(300, cutoff / 5), at + dur);
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(peak, at + 0.006);
  g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
  osc.connect(lp).connect(g).connect(ac.destination);
  osc.start(at);
  osc.stop(at + dur + 0.02);
}

// Tier 0..7: a quick up-arpeggio, higher and longer as the combo grows.
export function comboSting(tier) {
  const ac = audioContext();
  if (!ac) return;
  const t0 = ac.currentTime + 0.01, root = 330 * Math.pow(2, Math.min(tier, 7) / 12 * 2);
  const steps = [1, 1.26, 1.5, 2].slice(0, 2 + Math.min(2, Math.floor(tier / 2)));
  steps.forEach((ratio, i) => {
    for (const detune of [-8, 8]) {
      voice(ac, { freq: root * ratio * Math.pow(2, detune / 1200), at: t0 + i * 0.055, dur: 0.22 + tier * 0.02, peak: 0.07 });
    }
  });
  voice(ac, { type: "square", freq: root * 4, to: root * 8, at: t0 + steps.length * 0.055, dur: 0.18, peak: 0.03, cutoff: 8000 });
}

// A wrong key: a soft, quick "wah-wah" (the sad trombone, shortened), at most one every 350 ms.
let lastOops = 0;
export function oops() {
  const ac = audioContext();
  if (!ac || ac.currentTime - lastOops < 0.35) return;
  const t0 = ac.currentTime + 0.01;
  lastOops = t0;
  voice(ac, { type: "triangle", freq: 330, to: 294, at: t0, dur: 0.14, peak: 0.07, cutoff: 1800 });
  voice(ac, { type: "triangle", freq: 262, to: 196, at: t0 + 0.15, dur: 0.26, peak: 0.07, cutoff: 1400 });
}

// Combo lost: a stuttering downward zap.
export function comboBreaker() {
  const ac = audioContext();
  if (!ac) return;
  const t0 = ac.currentTime + 0.01;
  for (let i = 0; i < 3; i++) {
    voice(ac, { type: "square", freq: 700 - i * 120, to: 90, at: t0 + i * 0.08, dur: 0.12, peak: 0.08, cutoff: 3000 });
  }
}

// Hybrid mode's bomb: a fuse tick per strike left, higher and brighter as it gets close (5 … 1).
export function fuseTick(left) {
  const ac = audioContext();
  if (!ac) return;
  const t0 = ac.currentTime + 0.005, f = 520 * Math.pow(2, (5 - Math.min(5, left)) / 5);
  voice(ac, { type: "square", freq: f, to: f * 1.5, at: t0, dur: 0.07, peak: 0.035 + (5 - left) * 0.008, cutoff: 5000 });
}

// A part starts again: a discreet two-note "here we go" (no count-in fanfare).
export function restartCue() {
  const ac = audioContext();
  if (!ac) return;
  const t0 = ac.currentTime + 0.01;
  voice(ac, { type: "triangle", freq: 660, at: t0, dur: 0.12, peak: 0.05, cutoff: 3000 });
  voice(ac, { type: "triangle", freq: 880, at: t0 + 0.1, dur: 0.16, peak: 0.05, cutoff: 3000 });
}
