// Song difficulty, tempo-weighted points, XP and levels (#2436).
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { parseMidi } from "../../web/app/src/lib/midifile.js";
import { songNotes } from "../../web/app/src/lib/highway.js";
import { songFeatures, difficulty } from "../../web/app/src/lib/difficulty.js";
import { runXp, levelOf, xpToNext, levelDifficulty, Progress } from "../../web/app/src/lib/progress.js";
import { Judge } from "../../web/app/src/lib/judge.js";

const ROOT = new URL("../../library/midi/", import.meta.url).pathname;
const starter = readdirSync(ROOT, { recursive: true }).filter(f => /\.midi?$/i.test(f)).map(f => {
  const s = parseMidi(new Uint8Array(readFileSync(ROOT + f)).buffer);
  const notes = songNotes(s.events, s.durationMs).map((n, i) => ({ ...n, i }));
  return { level: f.split("/")[0], f: songFeatures(notes) };
});
const mean = xs => xs.reduce((a, b) => a + b, 0) / xs.length;
const byLevel = level => starter.filter(s => s.level === level).map(s => difficulty(s.f));

test("difficulty: the starter levels line up", () => {
  const [homer, first, beg, mid, adv] = ["0-homer", "1-first-steps", "2-beginner", "3-intermediate", "4-advanced"].map(byLevel);
  assert.ok(Math.max(...homer) <= 1.8 && Math.max(...first) <= 3, `${homer} / ${first}`);
  assert.ok(Math.max(...homer) < Math.min(...first), "every first step is harder than every homer song");
  assert.ok(Math.max(...first) < Math.min(...beg, ...mid, ...adv), "the real pieces are all harder");
  assert.ok(mean(beg) < mean(mid) && mean(mid) < mean(adv), `means ${mean(beg)} < ${mean(mid)} < ${mean(adv)}`);
  assert.ok([...homer, ...first, ...beg, ...mid, ...adv].every(d => d >= 1 && d <= 10));
});

test("difficulty: the tempo moves it", () => {
  const f = starter.find(s => s.level === "3-intermediate").f;
  assert.ok(difficulty(f, 0.5) < difficulty(f, 1) && difficulty(f, 1) < difficulty(f, 1.5));
  assert.equal(difficulty({ density: 0, chords: 0, hands: 0, black: 0, effort: 0 }), 1);
});

test("points: linear in the notes, weighted by the tempo", () => {
  const notes = [0, 1000, 2000, 3000].map((start, i) => ({ note: 60, start, end: start + 300, i }));
  const at = tempo => { const j = new Judge(notes, { tempo }); j.reset(0); j.press(60, 0); return j.score; };
  assert.equal(at(1), 102);
  assert.equal(at(0.5), 51);
  assert.equal(at(1.5), 153);
});

test("XP: judged notes × difficulty, less for easy songs and repeats, never negative", () => {
  const counts = { perfect: 10, good: 0, early: 0, late: 0, miss: 0, wrong: 3 };
  const full = runXp(counts, 5, 1, 1);
  assert.equal(full.xp, 100);                                   // 10 × 5 × 2
  assert.ok(runXp(counts, 5, 30, 1).xp < full.xp);             // easy for a level-30 player
  assert.equal(runXp(counts, 9, 30, 1).easy, 1);               // at or above the level: in full
  const repeats = [1, 2, 3, 4].map(k => runXp(counts, 5, 1, k).xp);
  assert.ok(repeats.every((x, k) => k === 0 || x < repeats[k - 1]), `${repeats}`);
  assert.equal(runXp({ perfect: 2, miss: 1 }, 5, 1, 1).xp, 0);   // too few notes judged
  assert.equal(runXp({ miss: 20, wrong: 40 }, 5, 1, 1).xp, 0);
});

test("levels: a growing curve, the level's difficulty rises", () => {
  assert.deepEqual(levelOf(0), { level: 1, into: 0, need: 100 });
  assert.deepEqual(levelOf(100), { level: 2, into: 0, need: xpToNext(2) });
  assert.equal(levelOf(100 + xpToNext(2) + 5).level, 3);
  assert.ok(xpToNext(10) > xpToNext(9));
  assert.equal(levelDifficulty(1), 1);
  assert.ok(levelDifficulty(10) > 4 && levelDifficulty(30) > 8 && levelDifficulty(80) <= 10);
});

test("progress: stored, repeats counted per day, level up reported", () => {
  const m = new Map(), store = { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) };
  let now = Date.parse("2026-09-13T10:00:00Z");
  const p = new Progress(store, "k", () => now);
  const r1 = p.award("a.mid", { perfect: 60 }, 2);
  assert.equal(r1.xp, 240);
  assert.equal(r1.levelUp, true);
  assert.equal(p.award("a.mid", { perfect: 60 }, 2).play, 2);
  assert.equal(new Progress(store, "k", () => now).xp, p.xp);
  now += 86400000;
  assert.equal(new Progress(store, "k", () => now).award("a.mid", { perfect: 60 }, 2).play, 1);   // a new day
  assert.equal(p.award("b.mid", { perfect: 1 }, 2).xp, 0);
});
