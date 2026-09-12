<script>
  // Live display (#659): keyboard + note names + chord, computed here on the phone.
  import { decodeFrame, NoteState } from "./lib/midi.js";
  import { detectChord, noteName } from "./lib/theory.js";
  import Keyboard from "./Keyboard.svelte";

  let { onFrame } = $props();
  const held = new NoteState();
  let sounding = $state([]);
  let raf = 0;

  const repaint = () => { raf = 0; sounding = held.sounding(); };    // at most one update per frame
  $effect(() => {
    const off = onFrame(buf => {
      if (buf === null) held.clear();
      else if (!held.apply(decodeFrame(buf))) return;
      if (!raf) raf = requestAnimationFrame(repaint);
    });
    return () => { off(); cancelAnimationFrame(raf); };
  });

  const chord = $derived(detectChord(sounding));
  const names = $derived(sounding.map(noteName).join(" "));
  const on = $derived(new Set(sounding));
</script>

<main>
  <div class="readout">
    <div class="chord">{chord || " "}</div>
    <div class="notes">{names || " "}</div>
  </div>
  <Keyboard {on} />
</main>

<style>
  main { flex: 1; display: flex; flex-direction: column; min-height: 0; }
  .readout { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 16px; }
  .chord { font-size: clamp(2.5rem, 14vw, 5rem); font-weight: 800; color: var(--yellow); }
  .notes { font-size: clamp(1rem, 5vw, 1.6rem); color: var(--muted); letter-spacing: 1px; }
</style>
