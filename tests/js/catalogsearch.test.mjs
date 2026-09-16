// The catalogue search in the browser (#2669) gives what web/catalog.py gives (same fixture as tests/test_score_catalog.py).
import test from "node:test";
import assert from "node:assert/strict";
import { CatalogIndex, searchParams } from "../../web/app/src/lib/catalogsearch.js";

const cat = new CatalogIndex({ source: "PDMX", scores: [
  { id: 1, title: "Nocturne Op. 9 No. 2", composer: "Chopin", period: "Romantic", categories: ["classical"], level: 4, hands: 2, popularity: 9, curated: true, file: "pdmx/1.mxl", tags: "" },
  { id: 2, title: "Swan Lake", composer: "Tchaikovsky", period: "Romantic", categories: ["classical"], level: 2, hands: 2, popularity: 12, curated: true, file: "pdmx/2.mxl", tags: "ballet" },
  { id: 3, title: "The Kesh", composer: "Traditional", period: "Traditional", categories: ["dances", "folk"], level: 1, hands: 1, popularity: 3, curated: false, file: "pdmx/3.mxl", tags: "jig" },
] });
const ids = r => r.items.map(s => s.id);

test("same answers as the Pi's search", () => {
  const r = cat.search();
  assert.deepEqual(ids(r), [2, 1]);
  assert.equal(r.size, 3);
  assert.deepEqual(ids(cat.search({ all: true })), [2, 1, 3]);
  assert.deepEqual(ids(cat.search({ q: "chop noct" })), [1]);
  assert.deepEqual(ids(cat.search({ q: "TCHAÏKOVSKI" })), [2]);
  assert.deepEqual(ids(cat.search({ q: "traditionnel" })), [3]);
  assert.deepEqual(ids(cat.search({ q: "jig" })), [3]);
  assert.equal(cat.search({ q: "danses" }).total, 1);
  assert.deepEqual(ids(cat.search({ category: "folk" })), [3]);
  assert.deepEqual(ids(cat.search({ level: 2 })), [2]);
  assert.deepEqual(ids(cat.search({ hands: 1 })), [3]);
  assert.deepEqual(ids(cat.search({ sort: "easy", all: true })), [3, 2, 1]);
  assert.deepEqual(ids(cat.search({ sort: "title", all: true })), [1, 2, 3]);
  const f = cat.search({ all: true }).facets;
  assert.deepEqual(f.categories, { classical: 2, dances: 1, folk: 1 });
  assert.equal(f.composers.Chopin, 1);
  assert.equal(cat.search({ all: true, offset: 1, limit: 1 }).items[0].id, 1);
  assert.equal("tags" in cat.search().items[0], false);
});

test("the /api/catalog parameters", () => {
  assert.deepEqual(searchParams("/api/catalog?q=chop&sort=nonsense&limit=abc&all=1&level=2"),
    { q: "chop", category: "", composer: "", period: "", level: 2, hands: 0, sort: "popular", offset: 0, limit: 40, all: true });
});
