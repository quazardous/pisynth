// Demo mode, phone side (#2416): stream a song to pisynth in short look-ahead batches. The Pi
// plays them on its own clock (steady rhythm whatever the Wi-Fi does). Pure logic: `send` and
// `now` are injected, so it is unit-tested under Node.

export class DemoSender {
  constructor({ events, send, now = () => performance.now(), lookaheadMs = 600, tempo = 1 }) {
    this.events = events;                 // [{ms, status, d1, d2}] sorted by ms
    this.send = send;
    this.now = now;
    this.lookaheadMs = lookaheadMs;
    this.tempo = tempo;
    this.playing = false;
  }

  // Start (or restart) at song position `fromMs`, at `tempo` (1 = as written).
  start(fromMs = 0, tempo = this.tempo) {
    this.tempo = tempo;
    this.origin = fromMs;
    this.startedAt = this.now();
    this.cursor = this.events.findIndex(e => e.ms >= fromMs);
    if (this.cursor < 0) this.cursor = this.events.length;
    this.playing = true;
    this.first = true;
    this.tick();
  }

  // Song position (ms, as written) at the phone's current time.
  position() {
    return this.playing ? this.origin + (this.now() - this.startedAt) * this.tempo : this.origin || 0;
  }

  // Timeline offset (ms since the demo started on the Pi) of a song event.
  offset(ev) {
    return (ev.ms - this.origin) / this.tempo;
  }

  // Send every event due within the look-ahead window. Call it regularly (e.g. every 150 ms).
  tick() {
    if (!this.playing) return false;
    const horizon = (this.now() - this.startedAt) + this.lookaheadMs;
    const batch = [];
    while (this.cursor < this.events.length && this.offset(this.events[this.cursor]) <= horizon && batch.length < 256) {
      const e = this.events[this.cursor++];
      batch.push([Math.round(this.offset(e) * 10) / 10, e.status, e.d1, e.d2]);
    }
    if (batch.length || this.first) {
      this.send({ t: "play", reset: this.first, ev: batch });
      this.first = false;
    }
    if (this.cursor >= this.events.length) this.done = true;
    return batch.length > 0;
  }

  stop() {
    if (this.playing) this.send({ t: "stop" });
    this.origin = this.position();
    this.playing = false;
  }
}
