// Synth settings from the phone (#2417): request/response over the companion socket + a
// throttle so dragging a slider sends a few updates, not hundreds. Pure, unit-tested under Node.

export class SynthApi {
  constructor(send) {
    this.send = send;                   // obj → bool
    this.pending = new Map();           // req id → resolve
    this.next = 1;
  }

  request(op, extra = {}, timeoutMs = 20000) {
    const req = this.next++;
    return new Promise(resolve => {
      if (!this.send({ t: "synth", op, req, ...extra })) { resolve({ ok: false, error: "not connected" }); return; }
      const timer = setTimeout(() => { this.pending.delete(req); resolve({ ok: false, error: "no answer" }); }, timeoutMs);
      this.pending.set(req, r => { clearTimeout(timer); resolve(r); });
    });
  }

  get() { return this.request("get"); }
  set(key, value) { return this.request("set", { key, value }); }

  // Feed every {"t":"synth"} message here; returns a pushed state (watch) or null.
  onMessage(msg) {
    if (msg.t !== "synth") return null;
    if (msg.req && this.pending.has(msg.req)) {
      this.pending.get(msg.req)(msg);
      this.pending.delete(msg.req);
      return msg.state || null;
    }
    return msg.state || null;
  }
}

// Leading + trailing throttle: fn runs at once, then at most every `ms` with the latest args.
export function throttle(fn, ms, { now = () => Date.now(), setT = setTimeout } = {}) {
  let last = -Infinity, timer = null, lastArgs = null;
  return (...args) => {
    lastArgs = args;
    const wait = last + ms - now();
    if (wait <= 0 && !timer) { last = now(); fn(...args); return; }
    if (!timer) timer = setT(() => { timer = null; last = now(); fn(...lastArgs); }, Math.max(0, wait));
  };
}
