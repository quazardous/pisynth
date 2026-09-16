// The score catalogue on the phone (#2657): search URLs, catalogue paths, loading a score, favourites and recents.
import test from "node:test";
import assert from "node:assert/strict";
import { catalogQuery, catalogPath, catalogId, isCatalogPath, loadCatalogSong, creditLine, ScoreShelf } from "../../web/app/src/lib/catalog.js";

const memory = () => { const m = new Map(); return { getItem: k => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }; };

test("search URLs leave the defaults out", () => {
  assert.equal(catalogQuery(), "/api/catalog");
  assert.equal(catalogQuery({ q: "  für elise ", category: "classical", level: 2, hands: 1, sort: "easy", offset: 40 }),
    "/api/catalog?q=f%C3%BCr+elise&category=classical&level=2&hands=1&sort=easy&offset=40");
  assert.equal(catalogQuery({ composer: "J. S. Bach", all: true }), "/api/catalog?composer=J.+S.+Bach&all=1");
});

test("catalogue paths", () => {
  assert.equal(catalogPath(42), "catalog:42");
  assert.equal(catalogId("catalog:42"), 42);
  assert.equal(catalogId("starter/x.mid"), null);
  assert.ok(isCatalogPath("catalog:1") && !isCatalogPath(undefined));
});

test("a catalogue score loads as a song with its credit", async () => {
  const xml = `<?xml version="1.0"?><score-partwise version="4.0"><part-list><score-part id="P1"/></part-list><part id="P1">
    <measure number="1"><attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note></measure></part></score-partwise>`;
  const fetcher = async url => { assert.equal(url, "/api/catalog/7.mxl"); return new Response(new TextEncoder().encode(xml)); };
  const item = { id: 7, title: "Air", composer: "Traditional", licence: "CC0", source: "https://musescore.com/score/7", level: 1, tags: "x" };
  const song = await loadCatalogSong(item, fetcher);
  assert.equal(song.path, "catalog:7");
  assert.equal(song.name, "Air");
  assert.equal(song.credit, "Traditional · CC0 · musescore.com/score/7");
  assert.ok(song.scoreXml.includes("score-partwise") && song.events.length === 2);
  assert.equal(song.catalog.tags, undefined);
  assert.equal(creditLine({ composer: "Chopin" }), "Chopin");
  await assert.rejects(loadCatalogSong(item, async () => new Response("", { status: 404 })), /404/);
});

test("favourites and recently played are kept, newest first", () => {
  const s = memory();
  const shelf = new ScoreShelf(s, "k", 2);
  assert.equal(shelf.toggleFav({ id: 1, title: "A", extra: 1 }), true);
  shelf.toggleFav({ id: 2, title: "B" });
  assert.deepEqual(new ScoreShelf(s, "k").fav.map(x => x.id), [2, 1]);
  assert.equal(shelf.toggleFav({ id: 1 }), false);
  for (const id of [1, 2, 1, 3]) shelf.played({ id, title: String(id) });
  assert.deepEqual(new ScoreShelf(s, "k").recent.map(x => x.id), [3, 1]);
  s.setItem("k", "{bad");
  assert.deepEqual(new ScoreShelf(s, "k").fav, []);
});
