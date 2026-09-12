<script>
  // Latency recorder (#659 / #2411): the mic records each key click and the synth's note; the
  // gap is measured here on the phone. MIDI frames only count hits — the timing comes from the
  // single recording (one clock), so network delay never enters the result.
  import { decodeFrame } from "./lib/midi.js";
  import { measureLatency } from "./lib/latency.js";

  let { onFrame } = $props();
  const TARGET = 10;
  let phase = $state("idle");                     // idle | recording | analysing | done
  let hits = $state(0);
  let error = $state("");
  let result = $state(null);
  let copied = $state(false);
  let rec = null;

  $effect(() => {
    const off = onFrame(buf => {
      const ev = buf && decodeFrame(buf);
      if (phase !== "recording" || !ev || ev.type !== "on") return;
      hits += 1;
      if (hits === TARGET) setTimeout(stop, 600);  // let the last note ring
    });
    return () => { off(); rec?.abort(); };
  });

  async function record() {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const chunks = [];
    proc.onaudioprocess = e => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    src.connect(proc);
    proc.connect(ctx.destination);
    const release = async () => { proc.disconnect(); src.disconnect(); stream.getTracks().forEach(t => t.stop()); await ctx.close(); };
    return {
      sampleRate: ctx.sampleRate,
      abort: release,
      async stop() {
        await release();
        const out = new Float32Array(chunks.reduce((a, c) => a + c.length, 0));
        let o = 0;
        for (const c of chunks) { out.set(c, o); o += c.length; }
        return out;
      },
    };
  }

  async function start() {
    error = ""; result = null; copied = false; hits = 0;
    try { rec = await record(); } catch (e) { error = "Microphone not available: " + e.message; return; }
    phase = "recording";
  }

  async function stop() {
    if (phase !== "recording" || !rec) return;
    phase = "analysing";
    const r = rec; rec = null;
    const samples = await r.stop();
    result = { ...measureLatency(samples, r.sampleRate), sampleRate: r.sampleRate };
    phase = "done";
  }

  const text = $derived(result && result.used
    ? `pisynth key→sound latency: ${result.median.toFixed(1)} ms (median of ${result.used}/${result.n} hits, ` +
      `range ${result.min}–${result.max} ms, MAD ${result.mad.toFixed(1)} ms)\n` +
      `measured ${new Date().toISOString().slice(0, 10)} with a phone mic @ ${result.sampleRate} Hz, ` +
      `includes speaker→mic travel (~3 ms per metre)\nper hit: ${result.gaps.join(", ")} ms`
    : "");

  const copy = () => navigator.clipboard.writeText(text).then(() => (copied = true));
</script>

<section class="card">
  <h1>Key → sound latency</h1>
  <ol>
    <li>Put the phone <b>between the keyboard and the speaker</b>, close to the keys.</li>
    <li>Press <b>Start</b>, then hit one key firmly <b>{TARGET} times</b>, about once a second.</li>
  </ol>
  <p class="muted">The phone hears each key's click, then the note: the gap is the latency. Everything is measured on the phone.</p>

  {#if phase === "recording"}
    <button onclick={stop}>Stop</button>
    <div class="big">{hits} / {TARGET}</div>
  {:else if phase === "analysing"}
    <div class="big">analysing…</div>
  {:else}
    <button onclick={start}>{phase === "done" ? "Measure again" : "Start"}</button>
  {/if}

  {#if error}<p class="error">{error}</p>{/if}
  {#if phase === "done"}
    {#if result.used}
      <div class="big">{result.median.toFixed(1)} ms</div>
      <pre>{text}</pre>
      <button onclick={copy}>{copied ? "Copied" : "Copy result"}</button>
    {:else}
      <p class="error">No clear key-click + note pairs found. Move the phone closer to the keys and hit harder.</p>
    {/if}
  {/if}
</section>

<style>
  ol { margin: 10px 0 10px 20px; }
  .big { font-size: 2rem; font-weight: 800; color: var(--yellow); margin-top: 14px; }
  pre { white-space: pre-wrap; margin-top: 14px; font-size: .85rem; }
  .error { color: #ff7a7a; margin-top: 12px; }
</style>
