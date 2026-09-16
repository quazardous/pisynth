import test from "node:test";
import assert from "node:assert/strict";
import { parseMidi, sampleSong } from "../../web/app/src/lib/midifile.js";
import { DemoSender } from "../../web/app/src/lib/demo.js";

// --- a tiny SMF writer for the tests ---
const vlq = n => { const out = [n & 0x7f]; while ((n >>= 7)) out.unshift((n & 0x7f) | 0x80); return out; };
const u32 = n => [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255];
const track = evs => { const body = evs.flatMap(([dt, ...bytes]) => [...vlq(dt), ...bytes]); return [..."MTrk"].map(c => c.charCodeAt(0)).concat(u32(body.length), body); };
const smf = (format, division, tracks) => new Uint8Array([..."MThd"].map(c => c.charCodeAt(0)).concat(u32(6), [0, format, 0, tracks.length, (division >> 8) & 255, division & 255], ...tracks)).buffer;

test("format 1 with a tempo map in track 0 and running status in track 1", () => {
  const t0 = track([[0, 0xff, 0x03, 4, ..."Song".split("").map(c => c.charCodeAt(0))],
                    [0, 0xff, 0x51, 3, 0x07, 0xa1, 0x20],        // 500000 µs/quarter = 120 bpm
                    [960, 0xff, 0x51, 3, 0x0f, 0x42, 0x40],      // after 2 quarters → 1000000 = 60 bpm
                    [0, 0xff, 0x2f, 0]]);
  const t1 = track([[0, 0x90, 60, 100], [480, 64, 90],            // running status: note on 64
                    [480, 0x80, 60, 0], [0, 0xb0, 64, 127], [0, 0xc0, 5],   // program change is skipped
                    [480, 0x90, 64, 0], [0, 0xff, 0x2f, 0]]);
  const song = parseMidi(smf(1, 480, [t0, t1]));
  assert.equal(song.name, "Song");
  assert.deepEqual(song.events.map(e => [Math.round(e.ms), e.status, e.d1, e.d2]),
    [[0, 0x90, 60, 100], [500, 0x90, 64, 90], [1000, 0x80, 60, 0], [1000, 0xb0, 64, 127], [2000, 0x90, 64, 0]]);
  assert.equal(Math.round(song.durationMs), 2000);
});

test("time signature: quarters per bar (#2658), 4 when absent", () => {
  const ts = (num, den) => parseMidi(smf(0, 480, [track([[0, 0xff, 0x58, 4, num, den, 24, 8], [0, 0xff, 0x2f, 0]])])).beatsPerBar;
  assert.equal(ts(3, 2), 3);                                         // 3/4
  assert.equal(ts(6, 3), 3);                                         // 6/8 = 3 quarters
  assert.equal(parseMidi(smf(0, 480, [track([[0, 0xff, 0x2f, 0]])])).beatsPerBar, 4);
});

test("rejects non-MIDI and SMPTE timing", () => {
  assert.throws(() => parseMidi(new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]).buffer), /not a MIDI file/);
  assert.throws(() => parseMidi(smf(0, 0xe728, [track([[0, 0xff, 0x2f, 0]])])), /SMPTE/);
});

test("sample song is sorted, balanced and uses the pedal", () => {
  const s = sampleSong();
  assert.ok(s.events.every((e, i, a) => !i || a[i - 1].ms <= e.ms));
  const ons = s.events.filter(e => e.status === 0x90).length, offs = s.events.filter(e => e.status === 0x80).length;
  assert.equal(ons, offs);
  assert.ok(s.events.some(e => e.status === 0xb0 && e.d1 === 64));
});

test("sender streams look-ahead batches, first with reset, scaled by tempo, and stops", () => {
  let now = 0;
  const sent = [];
  const events = [0, 250, 500, 750, 1000, 1250].map(ms => ({ ms, status: 0x90, d1: 60, d2: 90 }));
  const s = new DemoSender({ events, send: m => sent.push(m), now: () => now, lookaheadMs: 400 });
  s.start(0, 0.5);                                   // half tempo: song ms ×2 on the timeline
  assert.equal(sent[0].reset, true);
  assert.deepEqual(sent[0].ev.map(e => e[0]), [0]);  // 250 ms of song = 500 ms timeline > 400 look-ahead
  now = 300; s.tick();
  assert.deepEqual(sent[1].ev.map(e => e[0]), [500]);
  assert.equal(sent[1].reset, false);
  now = 1200; s.tick();
  assert.deepEqual(sent[2].ev.map(e => e[0]), [1000, 1500]);
  assert.ok(Math.abs(s.position() - 600) < 1e-9);    // 1200 ms at half tempo = 600 ms into the song
  s.stop();
  assert.deepEqual(sent.at(-1), { t: "stop" });
  s.start(750, 1);                                   // resume mid-song: offsets restart at 0
  assert.deepEqual(sent.at(-1).ev.map(e => e[0]), [0, 250]);
});
