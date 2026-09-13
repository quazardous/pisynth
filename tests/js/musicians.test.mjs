// Several musicians on one phone: four by default, renamable, their own data, old data kept for Musician 1.
import test from "node:test";
import assert from "node:assert/strict";
import { loadMusicians, saveMusicians, musicianKey, cleanName, KEY } from "../../web/app/src/lib/musicians.js";

const memory = (init = {}) => {
  const m = new Map(Object.entries(init));
  return { m, getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, String(v)), removeItem: k => m.delete(k) };
};

test("musicians: four by default, the first selected, what the phone had becomes Musician 1's", () => {
  const store = memory({ "pisynth.progress": '{"xp":375}', "pisynth.records": '{"a.mid":{"score":9}}' });
  const s = loadMusicians(store);
  assert.deepEqual(s.list.map(m => m.name), ["Musician 1", "Musician 2", "Musician 3", "Musician 4"]);
  assert.equal(new Set(s.list.map(m => m.color)).size, 4);          // a colour each
  assert.equal(s.current, "m1");
  assert.equal(store.getItem("pisynth.progress.m1"), '{"xp":375}');
  assert.equal(store.getItem("pisynth.records.m1"), '{"a.mid":{"score":9}}');
  assert.equal(store.getItem("pisynth.progress"), null);
  assert.equal(store.getItem("pisynth.endless.m1"), null);            // nothing to carry over
  assert.ok(store.getItem(KEY));
});

test("musicians: names and choice are kept, cleaned, and a broken save falls back to the defaults", () => {
  const store = memory();
  const s = loadMusicians(store);
  s.list[1].name = "Léa"; s.list[1].color = "#ffd23f"; s.list[2].color = "not-a-colour"; s.current = "m2";
  saveMusicians(s, store);
  const again = loadMusicians(store);
  assert.equal(again.list[1].name, "Léa");
  assert.equal(again.list[1].color, "#ffd23f");
  assert.equal(again.list[2].color, "#ff9f5a");                    // an unknown colour → Musician 3's default
  assert.equal(again.current, "m2");
  assert.equal(cleanName("   ", "Musician 3"), "Musician 3");
  assert.equal(cleanName("  David   B ", "x"), "David B");
  assert.equal(cleanName("x".repeat(40), "y").length, 24);
  assert.equal(musicianKey("pisynth.progress", "m3"), "pisynth.progress.m3");
  assert.equal(loadMusicians(memory({ [KEY]: '{"list":[{"id":"m1","name":""}],"current":"m9"}' })).current, "m1");
  assert.equal(loadMusicians(memory({ [KEY]: "{broken" })).list.length, 4);
});
