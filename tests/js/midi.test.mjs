import test from "node:test";
import assert from "node:assert/strict";
import { decodeFrame, NoteState } from "../../web/app/src/lib/midi.js";

const frame = (s, d1, d2, t = 0) => { const b = new ArrayBuffer(7); const v = new DataView(b); v.setUint8(0, s); v.setUint8(1, d1); v.setUint8(2, d2); v.setUint32(3, t); return b; };

test("decodes note on/off, velocity-0 note-on, CC, time", () => {
  assert.deepEqual(decodeFrame(frame(0x91, 60, 100, 123456)), { type: "on", note: 60, velocity: 100, channel: 1, t: 123456 });
  assert.equal(decodeFrame(frame(0x90, 60, 0)).type, "off");
  assert.equal(decodeFrame(frame(0x80, 60, 40)).type, "off");
  assert.deepEqual(decodeFrame(frame(0xb0, 64, 127)), { type: "cc", controller: 64, value: 127, channel: 0, t: 0 });
  assert.equal(decodeFrame(new ArrayBuffer(3)), null);
  assert.equal(decodeFrame(frame(0xe0, 0, 64)), null);
});

test("sustain pedal keeps released notes sounding until lifted", () => {
  const s = new NoteState();
  s.apply(decodeFrame(frame(0x90, 60, 90)));
  s.apply(decodeFrame(frame(0xb0, 64, 127)));
  s.apply(decodeFrame(frame(0x80, 60, 0)));
  s.apply(decodeFrame(frame(0x90, 64, 90)));
  assert.deepEqual(s.sounding(), [60, 64]);
  s.apply(decodeFrame(frame(0xb0, 64, 0)));
  assert.deepEqual(s.sounding(), [64]);
});
