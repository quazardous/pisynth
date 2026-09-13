// Arcade sound effects for the note highway (#2434), synthesised by the phone (Web Audio): a rising
// sting per combo tier and a glitchy "combo breaker". Short and quiet enough to sit over the piano.

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

// Combo lost: a stuttering downward zap.
export function comboBreaker() {
  const ac = audioContext();
  if (!ac) return;
  const t0 = ac.currentTime + 0.01;
  for (let i = 0; i < 3; i++) {
    voice(ac, { type: "square", freq: 700 - i * 120, to: 90, at: t0 + i * 0.08, dur: 0.12, peak: 0.08, cutoff: 3000 });
  }
}
