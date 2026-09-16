// Scores (#2657): the XML reader, MusicXML → a playable song (chords, ties, staves, tempo, repeats), .mxl,
// and our generated starter scores play exactly like their MIDI files.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { parseXml, child, kids, textOf } from "../../web/app/src/lib/xml.js";
import { scoreSong, scorePosition, playOrder, markKey } from "../../web/app/src/lib/musicxml.js";
import { readMxl, zipEntries } from "../../web/app/src/lib/mxl.js";
import { parseMidi } from "../../web/app/src/lib/midifile.js";
import { songNotes } from "../../web/app/src/lib/highway.js";

test("xml: elements, attributes, entities, CDATA, comments, doctype", () => {
  const root = parseXml(`<?xml version="1.0"?><!DOCTYPE x PUBLIC "a" "b"><!-- hi --><a k="1 &amp; 2"><b>R&#233;&lt;</b><c/><b><![CDATA[<raw>]]></b></a>`);
  assert.equal(root.name, "a");
  assert.equal(root.attrs.k, "1 & 2");
  assert.deepEqual(kids(root, "b").map(b => b.text), ["Ré<", "<raw>"]);
  assert.ok(child(root, "c"));
  assert.equal(textOf(root, "b"), "Ré<");
});

const score = (measures, extra = "") => `<?xml version="1.0"?><score-partwise version="4.0"><work><work-title>T</work-title></work>
<part-list><score-part id="P1"/></part-list><part id="P1">${measures}</part>${extra}</score-partwise>`;
const n = (step, oct, dur, more = "") => `<note><pitch><step>${step}</step><octave>${oct}</octave></pitch><duration>${dur}</duration>${more}</note>`;

test("musicxml: chords, ties, two staves, rests, tempo", () => {
  const xml = score(`<measure number="1"><attributes><divisions>2</divisions><time><beats>4</beats><beat-type>4</beat-type></time><staves>2</staves></attributes>
    <direction><direction-type><rehearsal>Verse</rehearsal></direction-type><sound tempo="60"/></direction>
    ${n("C", 4, 2, "<staff>1</staff>")}${n("E", 4, 2, "<chord/><staff>1</staff>")}
    ${n("G", 4, 6, '<tie type="start"/><staff>1</staff>')}
    <backup><duration>8</duration></backup>${n("C", 3, 8, "<staff>2</staff>")}</measure>
    <measure number="2">${n("G", 4, 2, '<tie type="stop"/><staff>1</staff>')}<note><rest/><duration>6</duration></note></measure>`);
  const s = scoreSong(xml);
  const notes = songNotes(s.events, s.durationMs);
  assert.equal(s.name, "T");
  assert.equal(s.bpm, 60);
  assert.deepEqual(notes.map(x => [x.note, x.start, x.end, x.track]),
    [[48, 0, 4000, 1], [60, 0, 1000, 0], [64, 0, 1000, 0], [67, 1000, 5000, 0]]);   // G tied over the bar: 4 beats
  assert.deepEqual(s.markers, [{ ms: 0, text: "Verse" }]);
  assert.equal(s.durationMs, 8000);
  assert.equal(s.beatsPerBar, 4);
  assert.equal(scorePosition(s.timeline, 6000), 1.5);            // half way through bar 2 = 1.5 whole notes
});

test("musicxml: repeats with first and second endings unfold", () => {
  const bar = (k, extra = "") => `<measure number="${k}">${extra}${n("C", 4, 4)}</measure>`;
  const xml = score(
    `<measure number="1"><attributes><divisions>1</divisions></attributes><barline location="left"><repeat direction="forward"/></barline>${n("C", 4, 4)}</measure>` +
    bar(2, '<barline location="left"><ending number="1" type="start"/></barline>').replace("</measure>", '<barline location="right"><ending number="1" type="stop"/><repeat direction="backward"/></barline></measure>') +
    bar(3, '<barline location="left"><ending number="2" type="start"/></barline>').replace("</measure>", '<barline location="right"><ending number="2" type="discontinue"/></barline></measure>') +
    bar(4));
  const s = scoreSong(xml);
  assert.equal(songNotes(s.events, s.durationMs).length, 5);    // 1 2 1 3 4
  assert.deepEqual(s.timeline.map(t => t.whole), [0, 1, 0, 2, 3]);
  assert.deepEqual(playOrder([{ forward: true }, { backward: true, times: 3 }, {}]), [0, 1, 0, 1, 0, 1, 2]);
  assert.throws(() => scoreSong("<score-timewise/>"), /timewise/);
  assert.throws(() => scoreSong("<html/>"), /not a MusicXML/);
});

test("mxl: the score inside the zip, stored or deflated", async () => {
  const enc = new TextEncoder();
  const xml = score(`<measure number="1"><attributes><divisions>1</divisions></attributes>${n("D", 4, 4)}</measure>`);
  const deflate = async bytes => new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate-raw"))).arrayBuffer());
  const files = [
    ["META-INF/container.xml", enc.encode('<container><rootfiles><rootfile full-path="song.musicxml"/></rootfiles></container>'), 0],
    ["song.musicxml", await deflate(enc.encode(xml)), 8],
  ];
  const chunks = [], central = [];
  let off = 0;
  const le = (v, n) => { const b = new Uint8Array(n); for (let i = 0; i < n; i++) b[i] = (v >>> (8 * i)) & 0xff; return b; };
  for (const [name, data, method] of files) {
    const nm = enc.encode(name);
    const local = [le(0x04034b50, 4), le(20, 2), le(0, 2), le(method, 2), le(0, 4), le(0, 4), le(data.length, 4), le(0, 4), le(nm.length, 2), le(0, 2), nm, data];
    central.push([le(0x02014b50, 4), le(20, 2), le(20, 2), le(0, 2), le(method, 2), le(0, 4), le(0, 4), le(data.length, 4), le(0, 4), le(nm.length, 2), le(0, 2), le(0, 2), le(0, 2), le(0, 2), le(0, 4), le(off, 4), nm]);
    for (const c of local) { chunks.push(c); off += c.length; }
  }
  const cdStart = off;
  for (const c of central.flat()) { chunks.push(c); off += c.length; }
  chunks.push(le(0x06054b50, 4), le(0, 2), le(0, 2), le(files.length, 2), le(files.length, 2), le(off - cdStart, 4), le(cdStart, 4), le(0, 2));
  const zip = new Uint8Array(chunks.reduce((s, c) => s + c.length, 0));
  let p = 0; for (const c of chunks) { zip.set(c, p); p += c.length; }
  assert.equal(zipEntries(zip).size, 2);
  assert.equal(await readMxl(zip.buffer), xml);
  assert.throws(() => zipEntries(new Uint8Array(40)), /not a zip/);
});

test("our starter scores play exactly like their MIDI files", () => {
  const root = new URL("../../library/midi/", import.meta.url).pathname;
  const scores = readdirSync(root, { recursive: true }).filter(f => f.endsWith(".musicxml"));
  assert.ok(scores.length >= 14, `${scores.length} scores`);
  for (const f of scores) {
    const s = scoreSong(readFileSync(root + f, "utf8"));
    const b = readFileSync(root + f.replace(/\.musicxml$/, ".mid"));
    const m = parseMidi(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
    const a = songNotes(s.events, s.durationMs), z = songNotes(m.events, m.durationMs);
    assert.equal(a.length, z.length, f);
    a.forEach((x, i) => {
      assert.equal(x.note, z[i].note, `${f} note ${i}`);
      assert.ok(Math.abs(x.start - z[i].start) < 1, `${f} note ${i}: ${x.start} vs ${z[i].start}`);
    });
    assert.equal(s.bpm, m.bpm, f);
    assert.deepEqual(s.markers.map(k => k.text), m.markers.map(k => k.text.replace(/^Part \d+ · /, "")), f);
  }
});

test("a played note finds its written note on the score (markKey), in every repeat", () => {
  const xml = score(`<measure number="1"><attributes><divisions>2</divisions><time><beats>2</beats><beat-type>4</beat-type></time></attributes>
    <barline location="left"><repeat direction="forward"/></barline>${n("C", 4, 2)}${n("E", 4, 1)}${n("G", 4, 1)}
    <barline location="right"><repeat direction="backward"/></barline></measure>`);
  const s = scoreSong(xml), notes = songNotes(s.events, s.durationMs);
  assert.equal(notes.length, 6);
  const keys = notes.map(x => markKey(scorePosition(s.timeline, x.start), x.note));
  assert.deepEqual(keys.slice(0, 3), ["0:60", "24:64", "36:67"]);         // in 96ths of a whole: a quarter, then an eighth
  assert.deepEqual(keys.slice(3), keys.slice(0, 3));                       // the repeat lands on the same notes
});
