"use strict";
// pisynth web companion — live MIDI display (#659).
// Connects to the Pi's WebSocket, lights up the keyboard as you play, and shows the note
// names + a best-effort chord name. All the work is here in the browser; the Pi only
// relays tiny {t,n,v} events (note on/off). No external library — stays light.

const LOW = 36, HIGH = 96;                 // shown range: C2..C7 (5 octaves)
const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const BLACK = [1, 3, 6, 8, 10];            // pitch classes that are black keys

const active = new Set();                  // MIDI note numbers currently held
const keyEl = {};                          // note number -> key element

function noteName(n) { return NAMES[n % 12] + (Math.floor(n / 12) - 1); }

// ---- keyboard ----
function buildKeyboard() {
  const kb = document.getElementById("keyboard");
  const whites = [];
  for (let n = LOW; n <= HIGH; n++) if (!BLACK.includes(n % 12)) whites.push(n);
  const W = 100 / whites.length;           // white-key width in %
  whites.forEach((n, i) => {
    const k = document.createElement("div");
    k.className = "key white";
    k.style.left = (i * W) + "%";
    k.style.width = W + "%";
    kb.appendChild(k);
    keyEl[n] = k;
  });
  // black keys sit between specific whites, offset right
  let wi = 0;
  for (let n = LOW; n <= HIGH; n++) {
    if (BLACK.includes(n % 12)) {
      const k = document.createElement("div");
      k.className = "key black";
      k.style.left = (wi * W - W * 0.3) + "%";
      k.style.width = (W * 0.6) + "%";
      kb.appendChild(k);
      keyEl[n] = k;
    } else { wi++; }
  }
}

function lite(n, on) {
  const k = keyEl[n];
  if (k) k.classList.toggle("on", on);
}

// ---- chord detection (best-effort) ----
const SHAPES = [
  [[0, 4, 7], "maj"], [[0, 3, 7], "min"], [[0, 3, 6], "dim"], [[0, 4, 8], "aug"],
  [[0, 4, 7, 10], "7"], [[0, 4, 7, 11], "maj7"], [[0, 3, 7, 10], "m7"],
  [[0, 3, 6, 10], "m7b5"], [[0, 3, 6, 9], "dim7"], [[0, 5, 7], "sus4"], [[0, 2, 7], "sus2"],
];
function detectChord(notes) {
  if (notes.length === 0) return "—";
  if (notes.length === 1) return noteName(notes[0]);
  const pcs = [...new Set(notes.map(n => n % 12))].sort((a, b) => a - b);
  for (const root of pcs) {
    const iv = pcs.map(p => (p - root + 12) % 12).sort((a, b) => a - b);
    for (const [shape, name] of SHAPES) {
      if (iv.length === shape.length && shape.every((v, i) => v === iv[i]))
        return NAMES[root] + " " + name;
    }
  }
  return pcs.map(p => NAMES[p]).join(" ");   // no match → list the pitch classes
}

function refresh() {
  const notes = [...active].sort((a, b) => a - b);
  document.getElementById("chord").textContent = detectChord(notes);
  document.getElementById("notes").textContent = notes.map(noteName).join(" ");
}

// ---- websocket ----
function connect() {
  const st = document.getElementById("status");
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { st.textContent = "live"; st.className = "status on"; };
  ws.onclose = () => {
    st.textContent = "reconnecting…"; st.className = "status off";
    active.clear(); Object.keys(keyEl).forEach(n => lite(+n, false)); refresh();
    setTimeout(connect, 1500);
  };
  ws.onmessage = (e) => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    if (m.t === "on") { active.add(m.n); lite(m.n, true); }
    else if (m.t === "off") { active.delete(m.n); lite(m.n, false); }
    refresh();
  };
}

buildKeyboard();
refresh();
connect();
