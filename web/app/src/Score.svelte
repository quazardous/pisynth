<script>
  // The loaded song's sheet music (#2657), drawn by OpenSheetMusicDisplay (loaded only when shown) on a
  // paper-white page. Each note carries its name, in English or French like the rest of the app, spelled
  // as the score writes it; a cursor follows the song (`position`: whole notes from the start of the score).
  // In "I play" the judged notes turn green (in time), orange (early/late) or red (missed): `marks`, by markKey.
  // `horizontal` (Score mode): the whole score on one line that scrolls under a fixed play line; a finger
  // slides it (`onSeek(whole)` as it moves, `onDrag(true|false)` when the drag starts and ends).
  import { onDestroy } from "svelte";
  import { spelledName } from "./lib/theory.js";
  import { markKey, xAtWhole, wholeAtX } from "./lib/musicxml.js";

  // names: the note names under the notes · zoom: the drawing's scale (1 = as OSMD draws it) · ended: the song is over (no play line)
  let { xml, position = 0, notation = "en", marks = new Map(), horizontal = false, onSeek = () => {}, onDrag = () => {},
        names = true, zoom = 1, ended = false } = $props();
  const MARK_COLORS = { good: "#1f9d55", off: "#e07b00", miss: "#d63030" };
  const PLAY_LINE = 0.3;                                         // horizontal: the play line, from the left
  let heads = new Map(), painted = new Map();                  // markKey → notehead SVG elements; key → colour shown
  const NS = "http://www.w3.org/2000/svg";
  let host = $state(null), error = $state(""), ready = $state(false);
  let osmd = null, width = 0, observer = null, measures = [];

  async function render() {
    ready = false; error = "";
    try {
      const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
      if (!host) return;
      host.innerHTML = "";
      osmd = new OpenSheetMusicDisplay(host, {
        autoResize: false, backend: "svg", drawingParameters: "compacttight", autoBeam: true,
        drawTitle: !horizontal, drawComposer: !horizontal, drawCredits: false, drawPartNames: false, followCursor: !horizontal,
        renderSingleHorizontalStaffline: horizontal,
      });
      await osmd.load(xml);
      draw();
      ready = true;
    } catch (err) { error = `This score can't be shown: ${err.message}`; }
  }

  function draw() {
    osmd.zoom = zoom;
    osmd.render();
    painted = new Map();                                        // a fresh drawing: nothing tinted yet
    labels();
    paintMarks();
    measures = horizontal ? layout() : [];
    osmd.cursor.show();
    seek(position, true);
    scroll(position);
  }

  // Horizontal: where each measure is drawn, in pixels, with its place in the score (whole notes).
  function layout() {
    const unit = 10 * (osmd.zoom || 1);
    const out = [];
    for (const row of osmd.GraphicSheet.MeasureList) {
      const m = row?.find(Boolean), src = m?.parentSourceMeasure, ps = m?.PositionAndShape;
      if (!src || !ps) continue;
      out.push({ whole: src.AbsoluteTimestamp.RealValue, len: src.Duration.RealValue, x: ps.AbsolutePosition.x * unit, width: ps.Size.width * unit });
    }
    return out.sort((a, b) => a.x - b.x);
  }

  // Note names under the noteheads.
  function labels() {
    const svg = host?.querySelector("svg");
    if (!svg || !osmd?.GraphicSheet) return;
    svg.querySelectorAll(".note-name").forEach(e => e.remove());
    heads = new Map();
    const withNames = names;
    for (const row of osmd.GraphicSheet.MeasureList) for (const measure of row) {
      for (const entry of measure?.staffEntries ?? []) for (const voice of entry.graphicalVoiceEntries) for (const gn of voice.notes) {
        const src = gn.sourceNote;
        if (!src || src.isRest() || !src.Pitch) continue;
        const head = gn.getNoteheadSVGs?.()?.[0];
        if (!head?.getBBox) continue;
        if (withNames) {
          const box = head.getBBox(), t = document.createElementNS(NS, "text");
          t.setAttribute("class", "note-name");
          t.setAttribute("x", String(box.x + box.width / 2));
          t.setAttribute("y", String(box.y + box.height + 9));
          t.textContent = spelledName(src.Pitch.FundamentalNote, src.Pitch.AccidentalHalfTones, notation);
          head.parentNode.appendChild(t);
        }
        const key = markKey(src.getAbsoluteTimestamp().RealValue, src.halfTone + 12);
        heads.set(key, [...(heads.get(key) ?? []), head]);
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

  // Horizontal: the score slides so that `whole` sits on the play line.
  function scroll(whole) {
    if (!horizontal || !host || dragging || !measures.length) return;
    host.scrollLeft = Math.max(0, xAtWhole(measures, whole));      // the drawing starts PLAY_LINE in: x under the line
  }

  // A finger slides the score (horizontal).
  let dragging = false, dragX = 0, dragLeft = 0, pointer = null;
  function down(e) {
    if (!horizontal || !ready || (e.pointerType === "mouse" && e.button !== 0)) return;
    dragging = false; dragX = e.clientX; dragLeft = host.scrollLeft; pointer = e.pointerId;
  }
  function move(e) {
    if (pointer !== e.pointerId) return;
    const dx = e.clientX - dragX;
    if (!dragging && Math.abs(dx) < 6) return;                   // a tap isn't a drag
    if (!dragging) { dragging = true; host.setPointerCapture?.(e.pointerId); onDrag(true); }
    host.scrollLeft = Math.max(0, dragLeft - dx);
    onSeek(Math.max(0, wholeAtX(measures, host.scrollLeft)));
  }
  function up(e) {
    if (pointer !== e.pointerId) return;
    pointer = null;
    if (dragging) { dragging = false; onDrag(false); }
  }

  // Colour the noteheads whose mark changed (and give back their ink to those no longer marked).
  function paintMarks() {
    for (const [key, color] of painted) if (marks.get(key) !== color) { tint(key, ""); painted.delete(key); }
    for (const [key, kind] of marks) if (painted.get(key) !== kind && heads.has(key)) { tint(key, MARK_COLORS[kind]); painted.set(key, kind); }
  }
  function tint(key, color) {
    for (const head of heads.get(key) ?? []) for (const el of head.querySelectorAll("path, ellipse, rect")) { el.style.fill = color; el.style.stroke = color; }
  }

  $effect(() => { xml; horizontal; if (host) render(); });
  $effect(() => { marks; if (ready) paintMarks(); });
  $effect(() => { const p = position; if (ready) { seek(p); scroll(p); } });
  $effect(() => { notation; names; if (ready) labels(); });
  $effect(() => { const z = zoom; if (ready && osmd && Math.abs((osmd.zoom || 1) - z) > 1e-3) draw(); });   // the size changed: draw again
  $effect(() => {                                              // redraw when the width changes (rotation, sheet)
    if (!host) return;
    observer = new ResizeObserver(() => {
      const w = host.clientWidth;
      if (horizontal) { width = w; if (ready) scroll(position); return; }   // one line: the width only moves the play line
      if (ready && Math.abs(w - width) > 8) { width = w; draw(); } else width = w;
    });
    observer.observe(host);
    return () => observer.disconnect();
  });
  onDestroy(() => { osmd = null; });
</script>

<div class="score" class:horizontal bind:this={host} role="region" aria-label="the score — slide it with a finger" onpointerdown={down} onpointermove={move} onpointerup={up} onpointercancel={up}></div>
{#if horizontal && ready && !ended}<div class="playline" style:left="{PLAY_LINE * 100}%" aria-hidden="true"></div>{/if}
{#if error}<p class="error">{error}</p>{:else if !ready}<p class="loading">Drawing the score…</p>{/if}

<style>
  .score { position: absolute; inset: 0; overflow-y: auto; overflow-x: hidden; background: #fbfaf5; color: #111; isolation: isolate;
           -webkit-user-select: none; user-select: none; }
  .score.horizontal { overflow: hidden; touch-action: pan-y; cursor: grab; display: flex; align-items: center; }
  /* room before and after the line, so its first and last notes can sit on the play line too */
  .score.horizontal :global(> div) { flex: 0 0 auto; margin-left: 30%; margin-right: 70%; }
  .playline { position: absolute; top: 8%; bottom: 8%; width: 3px; margin-left: -1px; border-radius: 2px; background: rgba(90,160,255,.55);
              box-shadow: 0 0 10px rgba(90,160,255,.45); pointer-events: none; z-index: 3; }
  /* OSMD puts its cursor at z-index -1, under its own page: lift it over the notes, blended so they show through */
  .score :global(img[id^="cursorImg"]) { z-index: 2 !important; mix-blend-mode: multiply; pointer-events: none; }
  .score :global(.note-name) { font: 700 9px system-ui, sans-serif; fill: #6b6b78; text-anchor: middle; }
  .loading, .error { position: absolute; left: 12px; right: 12px; top: 12px; color: #6b6b78; }
  .error { color: #c33; }
</style>
