// Listen on this device (#2670): the song played by the browser's piano (lib/demopiano.js) instead of pisynth's
// synth. It takes the same look-ahead batches DemoSender sends to the Pi ({t:"play", reset, ev:[[ms, status, d1, d2]]}
// and {t:"stop"}), so Listen works the same either way — with headphones on the phone, or when the synth is off.
// The GitHub Pages demo (#2669) listens this way too.

// A batch → [{at, on, note, velocity}]: `at` in performance.now() ms, from the song's start time `t0`. Pure, tested.
export function batchNotes(ev, t0) {
  const out = [];
  for (const [ms, status, d1, d2] of ev || []) {
    const kind = status & 0xf0;
    if (kind === 0x90 && d2 > 0) out.push({ at: t0 + ms, on: true, note: d1, velocity: d2 });
    else if (kind === 0x80 || kind === 0x90) out.push({ at: t0 + ms, on: false, note: d1, velocity: 0 });
  }
  return out;
}

export const LEAD_MS = 150;                          // like pisynth: the song starts this far ahead of the reset

// A `send` for DemoSender that plays on this device. onMessage gets the replies pisynth would give ({t:"demo", …}).
export function deviceListen(onMessage = () => {}) {
  const piano = import("./demopiano.js");
  const timers = new Set();
  let t0 = 0;
  const clear = () => { for (const id of timers) clearTimeout(id); timers.clear(); };
  return obj => {
    if (obj?.t === "play") {
      if (obj.reset) { clear(); t0 = performance.now() + LEAD_MS; onMessage({ t: "demo", state: "playing", lead_ms: LEAD_MS }); }
      piano.then(p => {
        const ac = p.context?.();
        for (const n of batchNotes(obj.ev, t0)) {
          // on the audio clock when there is one (steady), else a timer
          if (ac) { const when = ac.currentTime + Math.max(0, n.at - performance.now()) / 1000; n.on ? p.noteOn(n.note, n.velocity, when) : p.noteOff(n.note, when); }
          else { const id = setTimeout(() => { timers.delete(id); n.on ? p.noteOn(n.note, n.velocity) : p.noteOff(n.note); }, Math.max(0, n.at - performance.now())); timers.add(id); }
        }
      });
      return true;
    }
    if (obj?.t === "stop") {
      clear();
      piano.then(p => p.allOff());
      onMessage({ t: "demo", state: "stopped" });
      return true;
    }
    return false;
  };
}
