// Standard MIDI File → timed events (#2416), on the phone. Pure, unit-tested under Node.
// Formats 0/1, running status, tempo map (FF 51) applied across all tracks; SMPTE time is refused.
// Keeps note on/off and the sustain pedal (CC64) — what demo mode plays.

export function parseMidi(buffer) {
  const v = new DataView(buffer instanceof ArrayBuffer ? buffer : buffer.buffer);
  let p = 0;
  const str = n => { let s = ""; for (let i = 0; i < n; i++) s += String.fromCharCode(v.getUint8(p + i)); p += n; return s; };
  const u32 = () => { const x = v.getUint32(p); p += 4; return x; };
  const u16 = () => { const x = v.getUint16(p); p += 2; return x; };
  if (str(4) !== "MThd") throw new Error("not a MIDI file");
  const hlen = u32(), format = u16(), ntracks = u16(), division = u16();
  p += hlen - 6;
  if (division & 0x8000) throw new Error("SMPTE-timed MIDI files are not supported");
  const raw = [];                        // {tick, order, kind, status, d1, d2, tempo}
  let order = 0, name = "";
  for (let t = 0; t < ntracks && p < v.byteLength; t++) {
    if (str(4) !== "MTrk") throw new Error("bad track header");
    const len = u32();                  // (read first: `p + u32()` would use p before u32 advances it)
    const end = p + len;
    let tick = 0, running = 0;
    const vlq = () => { let x = 0, b; do { b = v.getUint8(p++); x = (x << 7) | (b & 0x7f); } while (b & 0x80); return x; };
    while (p < end) {
      tick += vlq();
      let status = v.getUint8(p);
      if (status < 0x80) status = running; else p++;
      if (status === 0xff) {
        const type = v.getUint8(p++), len = vlq();
        if (type === 0x51 && len === 3) raw.push({ tick, order: order++, kind: "tempo", tempo: (v.getUint8(p) << 16) | (v.getUint8(p + 1) << 8) | v.getUint8(p + 2) });
        if (type === 0x03 && !name && t <= 1) name = str(len); else p += len;
        continue;
      }
      if (status === 0xf0 || status === 0xf7) { p += vlq(); continue; }
      running = status;
      const kind = status & 0xf0;
      const d1 = v.getUint8(p++);
      const d2 = kind === 0xc0 || kind === 0xd0 ? 0 : v.getUint8(p++);
      if (kind === 0x90 || kind === 0x80 || (kind === 0xb0 && d1 === 64)) raw.push({ tick, order: order++, kind: "midi", status, d1, d2 });
    }
    p = end;
  }
  raw.sort((a, b) => a.tick - b.tick || (a.kind === "tempo" ? -1 : 0) - (b.kind === "tempo" ? -1 : 0) || a.order - b.order);
  let tempo = 500000, lastTick = 0, ms = 0;
  const events = [];
  for (const e of raw) {
    ms += ((e.tick - lastTick) * tempo) / division / 1000;
    lastTick = e.tick;
    if (e.kind === "tempo") tempo = e.tempo;
    else events.push({ ms, status: e.status, d1: e.d1, d2: e.d2 });
  }
  return { format, tracks: ntracks, name: name.trim(), events, durationMs: ms };
}

// A short built-in demo (no file needed): C major scale up, then I–vi–IV–V with the pedal.
export function sampleSong(bpm = 100) {
  const beat = 60000 / bpm, ev = [];
  const note = (t, n, len, vel = 90) => { ev.push({ ms: t, status: 0x90, d1: n, d2: vel }); ev.push({ ms: t + len, status: 0x80, d1: n, d2: 0 }); };
  [60, 62, 64, 65, 67, 69, 71, 72].forEach((n, i) => note(i * beat / 2, n, beat / 2 - 20));
  let t = 4 * beat + beat;
  for (const chord of [[48, 60, 64, 67], [45, 57, 60, 64], [41, 57, 60, 65], [43, 55, 59, 62]]) {
    ev.push({ ms: t, status: 0xb0, d1: 64, d2: 127 });
    chord.forEach((n, i) => note(t + i * 15, n, beat * 2 - 40, 80));
    ev.push({ ms: t + beat * 2 - 10, status: 0xb0, d1: 64, d2: 0 });
    t += beat * 2;
  }
  ev.sort((a, b) => a.ms - b.ms);
  return { name: "Sample: scale + I–vi–IV–V", events: ev, durationMs: t };
}
