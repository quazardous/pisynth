// Key-to-sound latency from ONE phone recording (#659 / #2411). Pure DSP, unit-tested under Node.
//
// Each key hit leaves two onsets in the recording: the key's mechanical click, then the
// synth's note coming out of the speaker. Both are captured by the same microphone, on the
// same clock, so the gap between them IS the latency (plus the sound's travel time from the
// speaker to the phone: ~3 ms per metre). The network is not involved.

// Short-time RMS envelope: one value per `hopMs`, over a `winMs` window.
export function envelope(samples, sampleRate, hopMs = 1, winMs = 3) {
  const hop = Math.max(1, Math.round(sampleRate * hopMs / 1000));
  const win = Math.max(hop, Math.round(sampleRate * winMs / 1000));
  const n = Math.floor((samples.length - win) / hop) + 1;
  const out = new Float32Array(Math.max(0, n));
  for (let i = 0; i < n; i++) {
    let s = 0;
    const o = i * hop;
    for (let j = 0; j < win; j++) { const x = samples[o + j]; s += x * x; }
    out[i] = Math.sqrt(s / win);
  }
  return out;
}

// Onsets = sharp energy rises: env[i] ≥ `ratio` × the mean of the preceding `lookMs`, and
// clearly above the recording's noise floor. Returns [{t (ms), peak}] with a refractory gap.
export function detectOnsets(env, hopMs = 1, { ratio = 3, lookMs = 8, floorFactor = 4, refractoryMs = 3 } = {}) {
  if (!env.length) return [];
  const sorted = Float32Array.from(env).sort();
  const floor = sorted[Math.floor(sorted.length * 0.2)] || 1e-9;
  const look = Math.max(1, Math.round(lookMs / hopMs));
  const refr = Math.max(1, Math.round(refractoryMs / hopMs));
  const onsets = [];
  let last = -Infinity;
  for (let i = look; i < env.length; i++) {
    let prev = 0;
    for (let j = i - look; j < i; j++) prev += env[j];
    prev /= look;
    if (env[i] > floorFactor * floor && env[i] >= ratio * Math.max(prev, floor) && i - last >= refr) {
      let peak = env[i];
      for (let j = i; j < Math.min(env.length, i + Math.round(20 / hopMs)); j++) peak = Math.max(peak, env[j]);
      onsets.push({ t: i * hopMs, peak });
      last = i;
    }
  }
  return onsets;
}

// Group onsets into hits (a new hit starts after `hitGapMs` of no onset), then per hit take
// the first onset as the click and the strongest onset `minGapMs`..`maxGapMs` later as the note.
export function pairHits(onsets, { minGapMs = 5, maxGapMs = 150, hitGapMs = 250 } = {}) {
  const hits = [];
  let cur = [];
  for (const o of onsets) {
    if (cur.length && o.t - cur[cur.length - 1].t > hitGapMs) { hits.push(cur); cur = []; }
    cur.push(o);
  }
  if (cur.length) hits.push(cur);
  const gaps = [];
  for (const h of hits) {
    const click = h[0];
    const candidates = h.filter(o => o.t - click.t >= minGapMs && o.t - click.t <= maxGapMs);
    if (!candidates.length) continue;
    const note = candidates.reduce((a, b) => (b.peak > a.peak ? b : a));
    gaps.push(note.t - click.t);
  }
  return gaps;
}

// Median + spread, dropping outliers further than 3 MADs from the median.
export function summarize(gaps) {
  if (!gaps.length) return { n: 0, used: 0, median: null, mad: null, min: null, max: null, gaps: [] };
  const med = a => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
  const m = med(gaps);
  const mad = med(gaps.map(g => Math.abs(g - m)));
  const kept = gaps.filter(g => Math.abs(g - m) <= 3 * Math.max(mad, 1));
  return { n: gaps.length, used: kept.length, median: med(kept), mad, min: Math.min(...kept), max: Math.max(...kept), gaps };
}

export function measureLatency(samples, sampleRate, opts = {}) {
  const hopMs = opts.hopMs || 1;
  return summarize(pairHits(detectOnsets(envelope(samples, sampleRate, hopMs), hopMs, opts.onset), opts.pair));
}
