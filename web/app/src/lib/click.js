// Count-in played by the phone itself (#2418), modern-game style: "3 · 2 · 1 · GO!" — soft, round
// ticks with a touch of space on the beats before the song, then a whoosh into a wide chord hit with a
// sub thump when it starts. Web Audio only: a count-in needs nothing from pisynth.

let ctx = null, bus = null;

// The shared AudioContext; call from a tap (browsers only start audio after a user gesture).
export function audioContext() {
  const AC = globalThis.AudioContext || globalThis.webkitAudioContext;
  if (!AC) return null;
  ctx ??= new AC();
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

// performance.now() times of an n-beat count-in ending where the song starts. Pure, tested under Node.
export function countInTimes(songStart, beatMs, n = 3) {
  return Array.from({ length: n }, (_, k) => songStart - (n - k) * beatMs);
}

// Output with a short, filtered echo for a bit of space (a reverb-ish tail without an impulse file).
function output(ac) {
  if (bus) return bus;
  const master = ac.createGain(), delay = ac.createDelay(1), fb = ac.createGain(), tone = ac.createBiquadFilter(), wet = ac.createGain();
  master.gain.value = 0.9;
  delay.delayTime.value = 0.11;
  fb.gain.value = 0.28;
  tone.type = "lowpass";
  tone.frequency.value = 2600;
  wet.gain.value = 0.35;
  master.connect(ac.destination);
  master.connect(delay);
  delay.connect(tone).connect(fb).connect(delay);
  tone.connect(wet).connect(ac.destination);
  bus = master;
  return bus;
}

function envelope(ac, at, peak, attack, decay) {
  const g = ac.createGain();
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(peak, at + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, at + attack + decay);
  return g;
}

function noise(ac, seconds) {
  const buf = ac.createBuffer(1, Math.ceil(ac.sampleRate * seconds), ac.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  const src = ac.createBufferSource();
  src.buffer = buf;
  return src;
}

// A round tick: sine with a quick pitch drop + a soft sine an octave up.
function tick(ac, out, at, freq) {
  const nodes = [];
  for (const [f, peak, type] of [[freq, 0.5, "sine"], [freq * 2, 0.12, "sine"]]) {
    const osc = ac.createOscillator(), g = envelope(ac, at, peak, 0.004, 0.16);
    osc.type = type;
    osc.frequency.setValueAtTime(f * 1.25, at);
    osc.frequency.exponentialRampToValueAtTime(f, at + 0.03);
    osc.connect(g).connect(out);
    osc.start(at); osc.stop(at + 0.2);
    nodes.push(osc);
  }
  return nodes;
}

// GO: a noise whoosh rising into the beat, a wide detuned chord hit, and a sub thump.
function go(ac, out, at) {
  const nodes = [];
  const whoosh = noise(ac, 0.45), bp = ac.createBiquadFilter(), wg = ac.createGain();
  bp.type = "bandpass"; bp.Q.value = 1.2;
  bp.frequency.setValueAtTime(300, at - 0.35);
  bp.frequency.exponentialRampToValueAtTime(5000, at);
  wg.gain.setValueAtTime(0.0001, at - 0.35);
  wg.gain.exponentialRampToValueAtTime(0.25, at - 0.02);
  wg.gain.exponentialRampToValueAtTime(0.0001, at + 0.05);
  whoosh.connect(bp).connect(wg).connect(out);
  whoosh.start(at - 0.35); whoosh.stop(at + 0.1);
  nodes.push(whoosh);

  const lp = ac.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.setValueAtTime(7000, at);
  lp.frequency.exponentialRampToValueAtTime(700, at + 0.6);
  const chord = envelope(ac, at, 0.22, 0.008, 0.7);
  lp.connect(chord).connect(out);
  for (const f of [440, 554.37, 659.25, 880]) {                  // A major, spread
    for (const detune of [-9, 9]) {
      const osc = ac.createOscillator();
      osc.type = "sawtooth"; osc.frequency.value = f; osc.detune.value = detune;
      osc.connect(lp); osc.start(at); osc.stop(at + 0.75);
      nodes.push(osc);
    }
  }

  const sub = ac.createOscillator(), sg = envelope(ac, at, 0.8, 0.003, 0.22);
  sub.type = "sine";
  sub.frequency.setValueAtTime(140, at);
  sub.frequency.exponentialRampToValueAtTime(48, at + 0.12);
  sub.connect(sg).connect(ac.destination);
  sub.start(at); sub.stop(at + 0.3);
  nodes.push(sub);
  return nodes;
}

// "3 · 2 · 1" ticks at `beatTimes`, "GO!" at `goTime` (performance.now() ms). Returns a cancel function.
export function scheduleCountdown(beatTimes, goTime) {
  const ac = audioContext();
  if (!ac) return () => {};
  const out = output(ac);
  const at = t => Math.max(ac.currentTime + 0.01, (t - performance.now()) / 1000 + ac.currentTime - (ac.outputLatency || 0));
  const nodes = beatTimes.flatMap(t => tick(ac, out, at(t), 988));             // B5, round and soft
  nodes.push(...go(ac, out, Math.max(at(goTime), ac.currentTime + 0.4)));
  return () => nodes.forEach(n => { try { n.stop(); } catch { /* already done */ } });
}
