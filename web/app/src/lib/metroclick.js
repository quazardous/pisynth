// The metronome click played by the phone (#2658): a short wooden tick, higher on beat 1, scheduled a
// little ahead on the audio clock so it stays steady whatever the page is doing. Also drives the beat
// lights, sound or not (pisynth playing the click: the phone only shows the beats).
import { audioContext } from "./click.js";

const LOOKAHEAD_MS = 160, PERIOD_MS = 40;

function tick(ac, at, accent, vol) {
  const peak = Math.max(0.0001, (vol / 100) * (accent ? 0.9 : 0.6));
  const osc = ac.createOscillator(), g = ac.createGain();
  osc.type = "triangle";
  osc.frequency.setValueAtTime(accent ? 1760 : 1245, at);
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(peak, at + 0.002);
  g.gain.exponentialRampToValueAtTime(0.0001, at + 0.07);
  osc.connect(g).connect(ac.destination);
  osc.start(at); osc.stop(at + 0.09);
  return osc;
}

// nextBeat(afterMs) → {at, n} the first beat after a performance.now() time (n = 1 on a bar line), or null.
// sound() → whether to click (else lights only); vol() → 0..100; onBeat(n) runs as each beat sounds.
export function startClicker({ nextBeat, sound = () => true, vol = () => 80, onBeat = () => {} }) {
  let last = performance.now(), stopped = false;
  const nodes = new Set(), timers = new Set();
  const cancel = () => {
    for (const n of nodes) try { n.stop(); } catch { /* done */ }
    for (const t of timers) clearTimeout(t);
    nodes.clear(); timers.clear();
  };
  const pump = () => {
    if (stopped) return;
    const now = performance.now();
    const ac = sound() ? audioContext() : null;
    for (let guard = 0, b; guard < 64 && (b = nextBeat(last)) && b.at < now + LOOKAHEAD_MS; guard++) {
      if (!(b.at > last)) break;                                  // a grid that doesn't move on: stop here
      last = b.at;
      if (b.at < now - 30) continue;                              // too late for this one (a paused tab)
      if (ac?.state === "running") {
        const when = Math.max(ac.currentTime, (b.at - performance.now()) / 1000 + ac.currentTime - (ac.outputLatency || 0));
        const node = tick(ac, when, b.n === 1, vol());
        nodes.add(node);
        node.onended = () => nodes.delete(node);
      }
      const id = setTimeout(() => { timers.delete(id); if (!stopped) onBeat(b.n); }, Math.max(0, b.at - now));
      timers.add(id);
    }
  };
  const timer = setInterval(pump, PERIOD_MS);
  pump();
  return {
    // The grid changed (tempo, beats): forget what was planned past now and plan again.
    replan() {
      cancel();
      last = performance.now();
      pump();
    },
    stop() {
      stopped = true;
      clearInterval(timer);
      cancel();
    },
  };
}
