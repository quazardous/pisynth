// A MusicXML score → a song the player can play (#2657), the same shape parseMidi() gives: timed note
// events, bpm, markers (the score's rehearsal marks: its parts), duration — plus a timeline mapping song ms
// to the score's own position, for the cursor. Pure; tested under Node.
//
// What it follows: parts and their staves (a piano part's staves are its two hands: one track each),
// divisions, chords, ties, backup/forward, grace notes (skipped), tempo marks, repeats with 1st/2nd endings.

import { parseXml, child, kids, textOf, numOf } from "./xml.js";

const STEP = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const DEFAULT_BPM = 120;
const MAX_MEASURES = 5000;                                     // after repeats: a runaway guard

// One measure of the first part: its length, marks and repeat signs (in quarters from its start).
function measureInfo(measure, divisions) {
  let pos = 0, len = 0, divs = divisions;
  const tempos = [], marks = [], info = { forward: false, backward: false, times: 2, endingStart: null, endingStop: false };
  for (const el of measure.children) {
    if (el.name === "attributes") {
      const d = numOf(el, "divisions", 0);
      if (d > 0) divs = d;
      const time = child(el, "time");
      if (time && !info.beats) { info.beats = numOf(time, "beats", 4); info.beatType = numOf(time, "beat-type", 4); }
    } else if (el.name === "note") {
      if (child(el, "grace")) continue;
      const d = numOf(el, "duration", 0) / divs;
      if (!child(el, "chord")) { pos += d; len = Math.max(len, pos); }
    } else if (el.name === "backup") pos -= numOf(el, "duration", 0) / divs;
    else if (el.name === "forward") { pos += numOf(el, "duration", 0) / divs; len = Math.max(len, pos); }
    else if (el.name === "direction") {
      const sound = child(el, "sound"), per = child(child(child(el, "direction-type"), "metronome"), "per-minute");
      const bpm = Number(sound?.attrs.tempo) || (per ? Number(per.text) : 0);
      if (bpm > 0) tempos.push({ q: pos, bpm });
      for (const dt of kids(el, "direction-type")) for (const r of kids(dt, "rehearsal")) if (r.text.trim()) marks.push({ q: pos, text: r.text.trim() });
    } else if (el.name === "sound" && Number(el.attrs.tempo) > 0) tempos.push({ q: pos, bpm: Number(el.attrs.tempo) });
    else if (el.name === "barline") {
      const rep = child(el, "repeat"), end = child(el, "ending");
      if (rep?.attrs.direction === "forward") info.forward = true;
      if (rep?.attrs.direction === "backward") { info.backward = true; info.times = Number(rep.attrs.times) || 2; }
      if (end?.attrs.type === "start") info.endingStart = String(end.attrs.number || "1").split(/[,\s]+/).map(Number).filter(Boolean);
      if (end && (end.attrs.type === "stop" || end.attrs.type === "discontinue")) info.endingStop = true;
    }
  }
  const implicit = Number(measure.attrs.number) === 0 || measure.attrs.implicit === "yes";
  return { len: len || (info.beats ? (info.beats * 4) / (info.beatType || 4) : 4), divs, tempos, marks, implicit, ...info };
}

// The order the measures are played in, repeats and endings unfolded. Pure (exported for the tests).
export function playOrder(infos) {
  let ending = null;
  const endings = infos.map(m => {                              // which pass numbers each measure belongs to
    if (m.endingStart) ending = m.endingStart;
    const here = ending;
    if (m.endingStop) ending = null;
    return here;
  });
  const order = [];
  let i = 0, repeatStart = 0, pass = 1;
  while (i < infos.length && order.length < MAX_MEASURES) {
    const m = infos[i];
    if (m.forward && pass === 1) repeatStart = i;
    if (endings[i] && !endings[i].includes(pass)) { i++; continue; }
    order.push(i);
    if (m.backward) {
      if (pass < m.times) { pass++; i = repeatStart; continue; }
      pass = 1; repeatStart = i + 1;
    }
    i++;
  }
  return order;
}

const midiOf = pitch => (numOf(pitch, "octave", 4) + 1) * 12 + STEP[textOf(pitch, "step")] + Math.round(numOf(pitch, "alter", 0));

// MusicXML text → {name, events, markers, bpm, beatsPerBar, durationMs, timeline, score: true}
export function scoreSong(xmlText, { name = "" } = {}) {
  const root = parseXml(xmlText);
  if (root.name === "score-timewise") throw new Error("timewise MusicXML isn't supported");
  if (root.name !== "score-partwise") throw new Error("not a MusicXML score");
  const parts = kids(root, "part");
  if (!parts.length) throw new Error("the score has no parts");
  const title = textOf(child(root, "work"), "work-title") || textOf(root, "movement-title") || name;

  // the first part sets the measures' lengths, the tempo, the marks and the repeats
  let divs = 1;
  const infos = kids(parts[0], "measure").map(m => { const info = measureInfo(m, divs); divs = info.divs; return info; });
  const order = playOrder(infos);
  const startQ = [];                                             // in playing order: where each played measure starts
  let q = 0;
  for (const idx of order) { startQ.push(q); q += infos[idx].len; }
  const totalQ = q;

  // tempo map (quarters → ms)
  const tempos = [];
  order.forEach((idx, k) => { for (const t of infos[idx].tempos) tempos.push({ q: startQ[k] + t.q, bpm: t.bpm }); });
  if (!tempos.length || tempos[0].q > 0) tempos.unshift({ q: 0, bpm: tempos[0]?.bpm ?? DEFAULT_BPM });
  const segs = [];
  let ms = 0;
  tempos.forEach((t, k) => {
    const next = tempos[k + 1]?.q ?? Infinity;
    segs.push({ q: t.q, ms, bpm: t.bpm });
    if (Number.isFinite(next)) ms += ((next - t.q) * 60000) / t.bpm;
  });
  const toMs = x => { let s = segs[0]; for (const g of segs) { if (g.q <= x) s = g; else break; } return s.ms + ((x - s.q) * 60000) / s.bpm; };

  // notes of every part, in playing order
  const notes = [], open = new Map();                           // ties waiting for their "stop": key → note
  parts.forEach((part, p) => {
    const measures = kids(part, "measure");
    let divisions = 1;
    const divsAt = measures.map(m => {                          // divisions in force at each measure's start
      const here = divisions;
      for (const a of kids(m, "attributes")) { const d = numOf(a, "divisions", 0); if (d > 0) divisions = d; }
      return here;
    });
    order.forEach((idx, k) => {
      const measure = measures[idx];
      if (!measure) return;
      let d = divsAt[idx], pos = startQ[k], lastStart = pos;
      for (const el of measure.children) {
        if (el.name === "attributes") { const v = numOf(el, "divisions", 0); if (v > 0) d = v; }
        else if (el.name === "backup") pos -= numOf(el, "duration", 0) / d;
        else if (el.name === "forward") pos += numOf(el, "duration", 0) / d;
        else if (el.name === "note") {
          if (child(el, "grace")) continue;
          const len = numOf(el, "duration", 0) / d;
          const start = child(el, "chord") ? lastStart : pos;
          if (!child(el, "chord")) { lastStart = pos; pos += len; }
          const pitch = child(el, "pitch");
          if (!pitch || child(el, "rest")) continue;
          const midi = midiOf(pitch), track = p * 2 + Math.max(0, numOf(el, "staff", 1) - 1), key = `${track}:${midi}`;
          const ties = kids(el, "tie").map(t => t.attrs.type);
          const held = open.get(key);
          if (ties.includes("stop") && held && Math.abs(held.end - start) < 1e-6) {
            held.end = start + len;                              // the tied note goes on
            if (!ties.includes("start")) open.delete(key);
            continue;
          }
          const note = { start, end: start + len, midi, track };
          notes.push(note);
          if (ties.includes("start")) open.set(key, note); else open.delete(key);
        }
      }
    });
  });

  const events = [];
  for (const n of notes) {
    if (n.end <= n.start) continue;
    const ch = n.track & 0x0f;
    events.push({ ms: toMs(n.start), status: 0x90 | ch, d1: n.midi, d2: 80, track: n.track });
    events.push({ ms: toMs(n.end), status: 0x80 | ch, d1: n.midi, d2: 0, track: n.track });
  }
  events.sort((a, b) => a.ms - b.ms || (a.status & 0xf0) - (b.status & 0xf0));   // note-offs before note-ons

  // the score's own position (in whole notes, repeats not unfolded) at each played measure, for the cursor
  const scoreQ = [];
  infos.reduce((s, m, i) => { scoreQ[i] = s; return s + m.len; }, 0);
  const timeline = order.map((idx, k) => ({ ms: toMs(startQ[k]), endMs: toMs(startQ[k] + infos[idx].len), whole: scoreQ[idx] / 4, lenWhole: infos[idx].len / 4 }));
  const markers = [];
  order.forEach((idx, k) => { for (const m of infos[idx].marks) markers.push({ ms: toMs(startQ[k] + m.q), text: m.text }); });
  const first = infos.find(m => m.beats);
  return {
    name: title, events, markers, timeline, score: true,
    bpm: Math.round(tempos[0].bpm), beatsPerBar: first ? first.beats : 4,
    durationMs: toMs(totalQ),
  };
}

// The score position (whole notes from its start) at song time `ms`, by the timeline.
export function scorePosition(timeline, ms) {
  if (!timeline?.length) return 0;
  let k = 0;
  while (k + 1 < timeline.length && timeline[k + 1].ms <= ms) k++;
  const t = timeline[k], span = Math.max(1, t.endMs - t.ms);
  return t.whole + Math.min(1, Math.max(0, (ms - t.ms) / span)) * t.lenWhole;
}
