<script>
  // The loaded song's sheet music (#2657), drawn by OpenSheetMusicDisplay (loaded only when shown) on a
  // paper-white page. Each note carries its name, in English or French like the rest of the app, spelled
  // as the score writes it; a cursor follows the song (`position`: whole notes from the start of the score).
  import { onDestroy } from "svelte";
  import { spelledName } from "./lib/theory.js";

  let { xml, position = 0, notation = "en" } = $props();
  const NS = "http://www.w3.org/2000/svg";
  let host = $state(null), error = $state(""), ready = $state(false);
  let osmd = null, width = 0, observer = null;

  async function render() {
    ready = false; error = "";
    try {
      const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
      if (!host) return;
      host.innerHTML = "";
      osmd = new OpenSheetMusicDisplay(host, {
        autoResize: false, backend: "svg", drawingParameters: "compacttight", autoBeam: true,
        drawTitle: true, drawComposer: true, drawCredits: false, drawPartNames: false, followCursor: true,
      });
      await osmd.load(xml);
      draw();
      ready = true;
    } catch (err) { error = `This score can't be shown: ${err.message}`; }
  }

  function draw() {
    osmd.render();
    labels();
    osmd.cursor.show();
    seek(position, true);
  }

  // Note names under the noteheads.
  function labels() {
    const svg = host?.querySelector("svg");
    if (!svg || !osmd?.GraphicSheet) return;
    svg.querySelectorAll(".note-name").forEach(e => e.remove());
    for (const row of osmd.GraphicSheet.MeasureList) for (const measure of row) {
      for (const entry of measure?.staffEntries ?? []) for (const voice of entry.graphicalVoiceEntries) for (const gn of voice.notes) {
        const src = gn.sourceNote;
        if (!src || src.isRest() || !src.Pitch) continue;
        const head = gn.getNoteheadSVGs?.()?.[0];
        if (!head?.getBBox) continue;
        const box = head.getBBox(), t = document.createElementNS(NS, "text");
        t.setAttribute("class", "note-name");
        t.setAttribute("x", String(box.x + box.width / 2));
        t.setAttribute("y", String(box.y + box.height + 9));
        t.textContent = spelledName(src.Pitch.FundamentalNote, src.Pitch.AccidentalHalfTones, notation);
        head.parentNode.appendChild(t);
      }
    }
  }

  // The cursor on the first note at or after `target` (the one coming next). The iterator is stepped on its
  // own and the cursor drawn once (cursor.next() redraws, and lays the page out, at every step).
  let shownAt = -1;
  function seek(target, restart = false) {
    const cursor = osmd?.cursor;
    let it = cursor?.Iterator;
    if (!it) return;
    const now = () => it.CurrentSourceTimestamp?.RealValue ?? 0;
    if (restart || now() > target + 1e-6) { cursor.reset(); it = cursor.Iterator; }
    for (let guard = 0; !it.EndReached && now() + 1e-6 < target && guard < 5000; guard++) it.moveToNextVisibleVoiceEntry(false);
    if (now() !== shownAt || restart) { shownAt = now(); cursor.update(); }
  }

  $effect(() => { xml; if (host) render(); });
  $effect(() => { const p = position; if (ready) seek(p); });
  $effect(() => { notation; if (ready) labels(); });
  $effect(() => {                                              // redraw when the width changes (rotation, sheet)
    if (!host) return;
    observer = new ResizeObserver(() => {
      const w = host.clientWidth;
      if (ready && Math.abs(w - width) > 8) { width = w; draw(); } else width = w;
    });
    observer.observe(host);
    return () => observer.disconnect();
  });
  onDestroy(() => { osmd = null; });
</script>

<div class="score" bind:this={host}></div>
{#if error}<p class="error">{error}</p>{:else if !ready}<p class="loading">Drawing the score…</p>{/if}

<style>
  .score { position: absolute; inset: 0; overflow-y: auto; overflow-x: hidden; background: #fbfaf5; color: #111; isolation: isolate;
           -webkit-user-select: none; user-select: none; }
  /* OSMD puts its cursor at z-index -1, under its own page: lift it over the notes, blended so they show through */
  .score :global(img[id^="cursorImg"]) { z-index: 2 !important; mix-blend-mode: multiply; pointer-events: none; }
  .score :global(.note-name) { font: 700 9px system-ui, sans-serif; fill: #6b6b78; text-anchor: middle; }
  .loading, .error { position: absolute; left: 12px; right: 12px; top: 12px; color: #6b6b78; }
  .error { color: #c33; }
</style>
