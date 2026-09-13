// Count-in played by the phone itself (#2418), video-game style: "3 · 2 · 1 · GO!" — three short
// square-wave blips on the beats before the song, then a brighter, longer chime when it starts.
// Web Audio only, so a count-in needs nothing from pisynth (no metronome sound, no round trip).

let ctx = null;

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

function tone(ac, at, freq, dur, peak, type = "square", slideTo = null) {
  const osc = ac.createOscillator(), gain = ac.createGain(), lp = ac.createBiquadFilter();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, at);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, at + dur * 0.6);
  lp.type = "lowpass";
  lp.frequency.value = 5000;                                   // soften the square wave a little
  gain.gain.setValueAtTime(0.0001, at);
  gain.gain.exponentialRampToValueAtTime(peak, at + 0.005);
  gain.gain.setValueAtTime(peak, at + dur * 0.7);
  gain.gain.exponentialRampToValueAtTime(0.0001, at + dur);
  osc.connect(lp).connect(gain).connect(ac.destination);
  osc.start(at);
  osc.stop(at + dur + 0.02);
  return osc;
}

// "3 · 2 · 1" blips at `beatTimes`, "GO!" at `goTime` (performance.now() ms). Returns a cancel function.
export function scheduleCountdown(beatTimes, goTime) {
  const ac = audioContext();
  if (!ac) return () => {};
  const at = t => Math.max(ac.currentTime, (t - performance.now()) / 1000 + ac.currentTime - (ac.outputLatency || 0));
  const nodes = beatTimes.map(t => tone(ac, at(t), 880, 0.14, 0.28));          // A5 blips
  const go = at(goTime);
  nodes.push(tone(ac, go, 1760, 0.45, 0.3, "square", 1760));                   // A6 "GO!"…
  nodes.push(tone(ac, go, 2217, 0.45, 0.16, "square"));                        // …with a major third on top
  nodes.push(tone(ac, go + 0.02, 440, 0.25, 0.12, "triangle"));                // and a little body
  return () => nodes.forEach(o => { try { o.stop(); } catch { /* already done */ } });
}
