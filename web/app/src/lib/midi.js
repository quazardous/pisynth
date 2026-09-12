// Binary MIDI frames from the Pi (#659): status u8 · data1 u8 · data2 u8 · t_ms u32, big-endian.
// Pure (no DOM) — unit-tested under Node.

export const FRAME_BYTES = 7;

export function decodeFrame(buf) {
  const v = buf instanceof DataView ? buf : new DataView(buf instanceof ArrayBuffer ? buf : buf.buffer, buf.byteOffset || 0, buf.byteLength);
  if (v.byteLength < FRAME_BYTES) return null;
  const status = v.getUint8(0), d1 = v.getUint8(1), d2 = v.getUint8(2), t = v.getUint32(3);
  const kind = status & 0xf0, channel = status & 0x0f;
  if (kind === 0x90 && d2 > 0) return { type: "on", note: d1, velocity: d2, channel, t };
  if (kind === 0x80 || kind === 0x90) return { type: "off", note: d1, channel, t };   // vel-0 note-on = off
  if (kind === 0xb0) return { type: "cc", controller: d1, value: d2, channel, t };
  return null;
}

// Held notes with the sustain pedal (CC64) folded in: a released key keeps sounding while
// the pedal is down, as the synth does.
export class NoteState {
  constructor() { this.down = new Set(); this.sustained = new Set(); this.pedal = false; }
  apply(ev) {
    if (!ev) return false;
    if (ev.type === "on") { this.down.add(ev.note); this.sustained.delete(ev.note); return true; }
    if (ev.type === "off") {
      this.down.delete(ev.note);
      if (this.pedal) this.sustained.add(ev.note);
      return true;
    }
    if (ev.type === "cc" && ev.controller === 64) {
      this.pedal = ev.value >= 64;
      if (!this.pedal) this.sustained.clear();
      return true;
    }
    return false;
  }
  sounding() { return [...new Set([...this.down, ...this.sustained])].sort((a, b) => a - b); }
  clear() { this.down.clear(); this.sustained.clear(); this.pedal = false; }
}
