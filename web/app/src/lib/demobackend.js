// The GitHub Pages demo (#2669): the web companion with no pisynth behind it. This stands in for the Pi, in the
// browser: the API calls are answered from static files (the starter set, a score catalogue subset searched here),
// the notes you play come from a MIDI keyboard on the computer (Web MIDI), the computer keys or taps on the on-screen
// keyboard, and a small Web Audio piano sounds them — and the songs in Listen. "Let the demo play" plays along like
// the dev stack's simulator. The routing and key mapping are pure, tested under Node.

// Demo or not is decided when the app starts (#2669): no pisynth answering → demo. A live binding, set by setDemo().
export let DEMO = false;
export function setDemo(on) { DEMO = !!on; }
export const BASE = import.meta.env?.BASE_URL ?? "/";
const HAS_DEMO_DATA = import.meta.env?.MODE === "demo";            // the Pages build carries the songs and scores

// Is a pisynth here? The /api/session answer → "pisynth" (paired or not, or restarting behind an error), "demo" (a plain
// web host: nothing of pisynth's), or "offline" (no answer at all, where there is no demo to fall back on).
export async function detectPisynth(fetchImpl = globalThis.fetch, hasDemoData = HAS_DEMO_DATA) {
  try {
    const r = await fetchImpl("/api/session", { credentials: "same-origin", cache: "no-store" });
    if (r.status === 204 || r.status === 401 || r.status >= 500) return "pisynth";
    return "demo";
  } catch {
    return hasDemoData ? "demo" : "offline";
  }
}

// ---- the API, from static files ----
// A request → what answers it: {static: path} (a file of the demo), {search: url} (the catalogue), {session} or {refused}.
export function demoRoute(url, method = "GET") {
  const path = new URL(url, "http://x").pathname;
  if (method !== "GET" && method !== "HEAD") return path === "/pair" ? { session: true } : { refused: true };
  if (path === "/api/session") return { session: true };
  if (path === "/api/midi") return { static: "demo/library.json" };
  if (path.startsWith("/api/midi/")) return { static: `demo/library/${path.slice("/api/midi/".length)}` };
  if (path === "/api/catalog") return { search: url };
  const m = path.match(/^\/api\/catalog\/(\d+)\.mxl$/);
  if (m) return { static: `demo/catalog/${m[1]}.mxl` };
  if (path === "/build.json" || path === "/version.json" || path === "/metronome-tick.wav") return { static: path.slice(1) };
  return null;                                    // anything else: the real fetch
}

// Keys of a computer keyboard → notes, laid out like a piano: the home row the white keys, the row above the black ones.
const KEYS = { a: 0, w: 1, s: 2, e: 3, d: 4, f: 5, t: 6, g: 7, y: 8, h: 9, u: 10, j: 11, k: 12, o: 13, l: 14, p: 15, ";": 16, "'": 17 };
export function keyNote(key, octave = 0) {
  const k = KEYS[(key || "").toLowerCase()];
  return k === undefined ? null : 60 + 12 * octave + k;
}

// One MIDI frame as pisynth sends it: status u8 · data1 u8 · data2 u8 · t_ms u32, big-endian.
export function encodeFrame(status, d1, d2, tMs) {
  const b = new ArrayBuffer(7), v = new DataView(b);
  v.setUint8(0, status); v.setUint8(1, d1); v.setUint8(2, d2); v.setUint32(3, (Math.round(tMs) >>> 0));
  return b;
}

// The dev simulator's playing, humanised: [[onMs, offMs, note]] from `inMs` → timed [atMs, on?, note, velocity],
// a little early or late, rarely missed.
export function simEvents(notes, inMs, { skill = 0.9, random = Math.random } = {}) {
  const out = [];
  for (const [on, off, note] of notes) {
    if (random() > 0.985 + (skill - 0.9) * 0.15) continue;          // now and then a note is missed
    const jitter = (random() - 0.5) * 2 * (1 - skill) * 180;
    const at = inMs + on + jitter;
    out.push([at, true, note, 64 + Math.floor(random() * 40)], [Math.max(at + 40, inMs + off + jitter), false, note, 0]);
  }
  return out.sort((a, b) => a[0] - b[0]);
}

// ---- in the browser ----
import { deviceListen } from "./devicelisten.js";
export const demoState = { autoplay: false, listeners: new Set() };

export function installDemo() {
  if (!DEMO) return;
  const realFetch = globalThis.fetch.bind(globalThis);
  let index = null;
  const catalog = async () => {
    if (!index) {
      const [{ CatalogIndex }, data] = await Promise.all([import("./catalogsearch.js"), realFetch(`${BASE}demo/catalog.json`).then(r => r.json())]);
      index = new CatalogIndex(data);
    }
    return index;
  };
  globalThis.fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    const route = demoRoute(url, (init.method || "GET").toUpperCase());
    if (!route) return realFetch(input, init);
    const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
    if (route.session) return new Response(null, { status: 204 });
    if (route.refused) return json({ error: "not in the demo — get pisynth to keep your own files" }, 403);
    if (route.search) {
      const { searchParams } = await import("./catalogsearch.js");
      return json((await catalog()).search(searchParams(route.search)));
    }
    return realFetch(`${BASE}${route.static}`, init);
  };
}

// The stand-in for pisynth's WebSocket (lib/pair.js openMidiSocket).
export function openDemoSocket({ onFrame, onState, onMessage = () => {} }) {
  let octave = 0, closed = false;
  const piano = import("./demopiano.js");
  const timers = new Set();
  const later = (ms, fn) => { const id = setTimeout(() => { timers.delete(id); fn(); }, Math.max(0, ms)); timers.add(id); };
  const clearTimers = () => { for (const id of timers) clearTimeout(id); timers.clear(); };

  // a note played: a frame for the app, a sound from the piano
  const play = (on, note, velocity = 90) => {
    if (closed || note < 21 || note > 108) return;
    onFrame(encodeFrame(on ? 0x90 : 0x80, note, on ? velocity : 0, performance.now()));
    piano.then(p => (on ? p.noteOn(note, velocity) : p.noteOff(note)));
  };
  demoState.play = play;

  const held = new Set();
  const typing = e => /^(input|select|textarea)$/i.test(e.target?.tagName) || e.target?.isContentEditable;
  const keydown = e => {
    if (typing(e) || e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "z") { octave = Math.max(-3, octave - 1); return; }
    if (e.key === "x") { octave = Math.min(3, octave + 1); return; }
    const n = keyNote(e.key, octave);
    if (n === null || held.has(e.code)) return;
    held.add(e.code); e.preventDefault();
    play(true, n);
    keyup.notes.set(e.code, n);
  };
  const keyup = e => {
    const n = keyup.notes.get(e.code);
    held.delete(e.code);
    if (n !== undefined) { keyup.notes.delete(e.code); play(false, n); }
  };
  keyup.notes = new Map();
  addEventListener("keydown", keydown);
  addEventListener("keyup", keyup);

  // a MIDI keyboard on the computer
  let midi = null;
  navigator.requestMIDIAccess?.().then(access => {
    midi = access;
    const hook = () => access.inputs.forEach(input => {
      input.onmidimessage = m => {
        const [st, d1, d2] = m.data, kind = st & 0xf0;
        if (kind === 0x90 && d2 > 0) play(true, d1, d2);
        else if (kind === 0x80 || kind === 0x90) play(false, d1);
      };
    });
    hook();
    access.onstatechange = hook;
  }).catch(() => {});

  const hello = () => onMessage({ t: "hello", sim: demoState.autoplay });
  demoState.listeners.add(hello);
  setTimeout(() => { onState("live"); hello(); }, 0);

  const listen = deviceListen(onMessage);
  return {
    send(obj) {
      if (closed || !obj) return false;
      if (obj.t === "sim") {                                       // "let the demo play": the song, played along
        if (!demoState.autoplay) return true;
        clearTimers();
        for (const [at, on, note, vel] of simEvents(obj.notes || [], obj.in_ms || 0)) later(at, () => play(on, note, vel));
      } else if (obj.t === "sim_stop") {
        clearTimers();
        piano.then(p => p.allOff());
      } else if (obj.t === "play" || obj.t === "stop") {           // Listen: the song through the browser's piano
        if (obj.t === "stop") clearTimers();
        listen(obj);
      } else if (obj.t === "synth") {                              // no synth settings: the metronome clicks on the phone
        setTimeout(() => onMessage({ t: "synth", op: obj.op, req: obj.req, ok: false, error: "no pisynth in the demo" }), 0);
      }
      return true;
    },
    close() {
      closed = true; clearTimers();
      removeEventListener("keydown", keydown); removeEventListener("keyup", keyup);
      demoState.listeners.delete(hello);
      midi?.inputs.forEach(i => { i.onmidimessage = null; });
    },
  };
}

export function setAutoplay(on) {
  demoState.autoplay = !!on;
  demoState.listeners.forEach(fn => fn());
}
