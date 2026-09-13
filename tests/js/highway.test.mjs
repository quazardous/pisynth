import test from "node:test";
import assert from "node:assert/strict";
import { keyX, keyRect, rangeView, toPct, keysInView, planView, FollowView } from "../../web/app/src/lib/viewport.js";
import { songNotes, noteRange, noteTracks, visibleNotes, timeToY } from "../../web/app/src/lib/highway.js";
import { Judge } from "../../web/app/src/lib/judge.js";
import { ClockSync } from "../../web/app/src/lib/clock.js";
import { parseMidi, sampleSong } from "../../web/app/src/lib/midifile.js";

// ---- viewport ----
test("key geometry: whites are 1 wide, blacks 0.6 on the boundary", () => {
  assert.equal(keyX(60), 35);                       // C4: 5 octaves × 7 whites
  assert.equal(keyX(62), 36);                       // D4
  assert.equal(keyX(61), 35.7);                     // C#4 straddles C|D
  assert.deepEqual(keyRect(66), { n: 66, black: true, x: 38.7, w: 0.6 });   // F#4 between F and G
  assert.equal(keyX(72) - keyX(60), 7);
});

test("range view covers the keys and maps them to percents like the old keyboard", () => {
  const v = rangeView(36, 96);                      // the previous fixed 5-octave keyboard
  assert.equal(v.span, 36);
  const c4 = toPct(keyRect(60), v), cs4 = toPct(keyRect(61), v);
  assert.ok(Math.abs(c4.left - (14 / 36) * 100) < 1e-9 && Math.abs(c4.width - 100 / 36) < 1e-9);
  assert.ok(Math.abs(cs4.left - (14.7 / 36) * 100) < 1e-9);
  assert.equal(rangeView(61, 70).x0, keyX(60));     // black edges widen to the white neighbour
  const keys = keysInView(v);
  assert.equal(keys[0].n, 36);
  assert.equal(keys.at(-1).n, 96);
});

test("plan: a narrow song is fixed and centred, a wide one follows", () => {
  const p = planView(60, 72, 390);                  // one octave on a phone
  assert.equal(p.mode, "fixed");
  assert.equal(p.span, 15);                         // widened to the 2-octave minimum
  assert.ok(p.x0 < keyX(60) && p.x0 + p.span > keyX(72) + 1);
});

test("plan: 3 octaves fit a 400 px portrait screen, 5 octaves don't; landscape fits 5", () => {
  assert.equal(planView(48, 83, 400).mode, "fixed");       // C3..B5 → C3..C6 = 22 whites ≤ 22
  const wide = planView(36, 96, 390);
  assert.equal(wide.mode, "follow");
  assert.ok(wide.span >= 15 && wide.span <= 21);
  assert.equal(planView(36, 96, 844).mode, "fixed");
});

test("follow window keeps active notes, fits the next ones, glides and clamps", () => {
  const f = new FollowView({ x0: keyX(60), span: 15 });
  assert.equal(f.aim([], [64, 67]), keyX(60));      // already visible: no move
  const t = f.aim([], [86, 88]);                    // two octaves up
  assert.ok(t + 15 >= keyX(88) + 1 && t <= keyX(86));
  const a = f.step(100).x0;
  assert.ok(a > keyX(60) && a < t);                 // gliding, not jumping
  for (let i = 0; i < 50; i++) f.step(100);
  assert.equal(f.x0, t);
  f.jump(keyX(60));
  const held = f.aim([48], [90, 91]);               // C3 held, far notes coming: C3 stays visible
  assert.ok(held <= keyX(48) && held + 15 >= keyX(48) + 1);
  f.jump(-100);
  assert.equal(f.x0, keyX(21));                     // clamped to A0
});

// ---- highway ----
test("song notes pair on/off per pitch and channel, FIFO, with tracks", () => {
  const ev = [
    { ms: 0, status: 0x90, d1: 60, d2: 90, track: 1 },
    { ms: 100, status: 0x90, d1: 60, d2: 80, track: 1 },      // same pitch again before the first ends
    { ms: 150, status: 0x91, d1: 60, d2: 70, track: 2 },      // other channel
    { ms: 200, status: 0x80, d1: 60, d2: 0 },
    { ms: 300, status: 0x90, d1: 60, d2: 0 },                  // vel-0 note-on = off
  ];
  const n = songNotes(ev, 1000);
  assert.deepEqual(n.map(x => [x.note, x.start, x.end, x.ch, x.track]), [[60, 0, 200, 0, 1], [60, 100, 300, 0, 1], [60, 150, 1000, 1, 2]]);
  assert.deepEqual(noteRange(n), { low: 60, high: 60 });
  assert.deepEqual(noteTracks(n), [1, 2]);
});

test("visible notes: overlap with the window, long notes that started earlier included", () => {
  const notes = songNotes(sampleSong(120).events, 10000);
  const t = 2600;
  const vis = visibleNotes(notes, t, 1000, 100);
  assert.ok(vis.length > 0);
  assert.ok(vis.every(n => n.end >= t - 100 && n.start <= t + 1000));
  const brute = notes.filter(n => n.end >= t - 100 && n.start <= t + 1000);
  assert.equal(vis.length, brute.length);
  assert.equal(timeToY(1500, 1000, 800, 0.2), 700);        // 500 ms ahead → 100 px above the line
});

test("parsed sample keeps tracks and bpm", () => {
  const s = sampleSong(90);
  assert.equal(s.bpm, 90);
  assert.ok(s.events.some(e => e.track === 1));
  assert.throws(() => parseMidi(new Uint8Array(8).buffer));
});

// ---- judge ----
const song = [
  { note: 60, start: 1000, end: 1400 }, { note: 64, start: 1000, end: 1400 },   // a chord
  { note: 67, start: 2000, end: 2400 }, { note: 60, start: 3000, end: 3400 },
];

test("judge: perfect / good / early / late / wrong, chords, streak and score", () => {
  const j = new Judge(song);
  assert.equal(j.press(60, 1030).kind, "perfect");
  assert.equal(j.press(64, 1090).kind, "good");
  assert.equal(j.press(64, 1100).kind, "wrong");            // already played
  assert.equal(j.streak, 0);
  const early = j.press(67, 1800);
  assert.equal(early.kind, "early");
  assert.equal(early.delta, -200);
  const before = j.score, wrong = j.press(62, 3000);
  assert.equal(wrong.kind, "wrong");
  assert.equal(wrong.penalty, 25);
  assert.equal(j.score, before - 25);
  assert.equal(j.press(60, 3200).kind, "late");
  assert.deepEqual(j.counts, { perfect: 1, good: 1, early: 1, late: 1, miss: 0, wrong: 2 });
  assert.equal(j.accuracy(), Math.round(((1 + 0.7 + 0.6) / 4) * 100));
  assert.ok(j.score > 0);
});

test("judge: misses once the window closes; windows scale with tempo; reset skips earlier notes", () => {
  const j = new Judge(song);
  assert.equal(j.press(61, 900).penalty, 0);                 // a wrong key never takes the score below 0
  assert.equal(j.score, 0);
  j.counts.wrong = 0;
  assert.deepEqual(j.advance(1200), []);
  assert.deepEqual(j.advance(1300), [0, 1]);                // 1000 + 260 passed
  assert.equal(j.counts.miss, 2);
  const slow = new Judge(song, { tempo: 0.5 });             // half speed: the windows stay a share of the beat
  assert.equal(slow.press(60, 1040).kind, "perfect");       // (±50 song ms = ±100 real ms)
  assert.equal(slow.press(64, 1060).kind, "good");
  slow.reset(1500);
  assert.equal(slow.press(60, 1000).kind, "wrong");         // before the loop start: out of play
  assert.equal(slow.press(67, 2010).kind, "perfect");
});

test("judge: windows follow the song's beat and the tempo slider, within real-ms bounds", () => {
  const at = (bpm, tempo) => new Judge([], { beatMs: 60000 / bpm, tempo });
  assert.equal(at(60, 1).realWindow("perfect"), 100);       // a slow song: 1/10 of a 1 s beat
  assert.equal(at(60, 1).realWindow("good"), 220);
  assert.equal(at(120, 1).realWindow("perfect"), 70);       // a fast one: the floor
  assert.equal(at(60, 0.5).realWindow("perfect"), 150);     // slower still: the ceiling
  assert.ok(at(80, 0.5).realWindow("good") > at(80, 1).realWindow("good"));
  assert.ok(at(80, 1.5).realWindow("good") < at(80, 1).realWindow("good"));
  for (const k of ["perfect", "good", "ok"]) assert.ok(at(90, 1).win(k) === at(90, 1).realWindow(k));
});

// ---- clock ----
test("clock sync keeps the fastest trip, forgets old samples, survives the u32 wrap", () => {
  const c = new ClockSync({ windowMs: 1000 });
  assert.equal(c.toLocal(5), null);
  c.observe(100, 5100);                                     // offset 5000 + 0 ms trip
  c.observe(200, 5230);                                     // 30 ms of Wi-Fi
  c.observe(300, 5310);
  assert.equal(c.offset, 5000);
  assert.equal(c.toLocal(250), 5250);
  c.observe(2000, 7040);                                    // 1 s later: the early samples expire
  assert.equal(c.offset, 5040);
  const w = new ClockSync();
  w.observe(2 ** 32 - 10, 1000);                            // just before the wrap
  w.observe(5, 1016);                                       // 15 ms of Pi time later, after it
  assert.equal(w.offset, 1010 - 2 ** 32);
  assert.equal(w.toLocal(5), 1015);
  assert.equal(w.toLocal(2 ** 32 - 10), 1000);
});
