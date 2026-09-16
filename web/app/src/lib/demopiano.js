// The GitHub Pages demo's sound (#2669): no pisynth there, so a small Web Audio piano plays what you press and the
// songs in Listen — a few decaying partials through a soft low-pass, brighter when struck harder. Browser only.
import { audioContext } from "./click.js";

let bus = null;
const voices = new Map();                        // note → {gain, oscs}

function output(ac) {
  if (bus) return bus;
  const lp = ac.createBiquadFilter(), comp = ac.createDynamicsCompressor(), master = ac.createGain();
  lp.type = "lowpass"; lp.frequency.value = 5200;
  master.gain.value = 0.5;
  lp.connect(comp).connect(master).connect(ac.destination);
  bus = lp;
  return bus;
}

const freq = n => 440 * 2 ** ((n - 69) / 12);

// Strike `note` at audio time `at` (seconds, default now), velocity 1–127.
export function noteOn(note, velocity = 90, at = null) {
  const ac = audioContext();
  if (!ac) return;
  const t = at ?? ac.currentTime;
  noteOff(note, t);
  const out = output(ac), g = ac.createGain(), v = Math.max(0.05, velocity / 127);
  const f = freq(note), decay = Math.max(0.6, 3.2 - (note - 48) * 0.04);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.35 * v, t + 0.004);
  g.gain.exponentialRampToValueAtTime(0.12 * v, t + 0.25);
  g.gain.exponentialRampToValueAtTime(0.0001, t + decay);
  g.connect(out);
  const oscs = [[1, 1, "triangle"], [2, 0.35 * v, "sine"], [3, 0.12 * v, "sine"], [4.01, 0.05 * v, "sine"]].map(([h, amp, type]) => {
    const o = ac.createOscillator(), og = ac.createGain();
    o.type = type; o.frequency.value = f * h; og.gain.value = amp;
    o.connect(og).connect(g);
    o.start(t); o.stop(t + decay + 0.05);
    return o;
  });
  voices.set(note, { g, oscs, t });
}

// Release `note` at audio time `at` (a short fade).
export function noteOff(note, at = null) {
  const ac = audioContext(), vo = voices.get(note);
  if (!ac || !vo) return;
  const t = Math.max(at ?? ac.currentTime, vo.t + 0.01);
  vo.g.gain.cancelScheduledValues(t);
  vo.g.gain.setTargetAtTime(0.0001, t, 0.08);
  for (const o of vo.oscs) { try { o.stop(t + 0.5); } catch { /* stopped */ } }
  voices.delete(note);
}

export function allOff() { for (const n of [...voices.keys()]) noteOff(n); }
