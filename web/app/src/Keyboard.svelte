<script>
  // On-screen keyboard (#659). Positions come from lib/viewport.js, the same mapping the note
  // highway uses (#2418), so a `view` ({x0, span} in white keys) can slide smoothly.
  import { keysInView, rangeView, toPct } from "./lib/viewport.js";
  import { DEMO, demoState } from "./lib/demobackend.js";
  import { noteName } from "./lib/theory.js";
  import { prefs } from "./lib/prefs.svelte.js";
  // on = your keys (blue) · demo = keys to light yellow · ghost = the perfect timing (#2429), drawn
  // as a translucent, outlined key that can overlap yours · fingers = Map note → {finger, color}: the
  // suggested finger, a numbered badge on the key (#2431)
  // moves = [{from: [notes], to: [notes], dir}]: a hand about to move — where it is (blue fingers), where it goes
  // (green fingers) and an arrow from one to the other
  let { low = 36, high = 96, view = null, on = new Set(), demo = new Set(), ghost = new Set(), fingers = null, moves = null, height = "34vh", minHeight = "150px" } = $props();

  const shown = $derived(view ?? rangeView(low, high));
  const layout = $derived(keysInView(shown).map(k => ({ ...k, ...toPct(k, shown) })));
  // Centre (percent) of a group of keys; the arrow of a move runs between its two groups.
  const centre = keys => {
    const at = layout.filter(k => keys.includes(k.n));
    return at.length ? at.reduce((s, k) => s + k.left + k.width / 2, 0) / at.length : null;
  };
  // The demo (#2669): the keys can be played with a finger or the mouse.
  const touching = new Map();                                    // pointer → note
  function press(e, n) { if (!DEMO) return; e.preventDefault(); touching.set(e.pointerId, n); demoState.play?.(true, n, 96); }
  function release(e) { const n = touching.get(e.pointerId); if (n === undefined) return; touching.delete(e.pointerId); demoState.play?.(false, n); }
  const arrows = $derived((moves || []).map(mv => ({ x1: centre(mv.from), x2: centre(mv.to), dir: mv.dir }))
    .filter(a => a.x2 !== null).map(a => ({ ...a, x1: a.x1 ?? a.x2 - a.dir * 6 })));
</script>

<div class="keyboard" aria-label="live keyboard" style:height style:min-height={minHeight}>
  {#each layout as k (k.n)}
    <div class="key" class:black={k.black} class:white={!k.black} class:on={on.has(k.n)} class:demo={demo.has(k.n) && !on.has(k.n)} class:ghost={ghost.has(k.n)}
         style:left="{k.left}%" style:width="{k.width}%"
         onpointerdown={e => press(e, k.n)} onpointerup={release} onpointerleave={release} onpointercancel={release} role="presentation">
      {#if !k.black && k.n % 12 === 0}<span class="octave">{noteName(k.n, prefs.notation)}</span>{/if}   <!-- each C names its octave (#2673) -->
      {#if fingers?.has(k.n)}<span class="finger {fingers.get(k.n).move}" class:thumb={fingers.get(k.n).finger === 1} style:--hand={fingers.get(k.n).color}>{fingers.get(k.n).finger}</span>{/if}
    </div>
  {/each}
  {#each arrows as a, i (i)}
    <div class="move" class:down={a.x2 < a.x1} style:left="{Math.min(a.x1, a.x2)}%" style:width="{Math.max(2, Math.abs(a.x2 - a.x1))}%"
         aria-label="move the hand {a.dir > 0 ? 'up' : 'down'}"></div>
  {/each}
</div>

<style>
  .keyboard { position: relative; background: var(--black); border-top: 2px solid #000; overflow: hidden; flex: 0 0 auto; }
  .key { position: absolute; top: 0; bottom: 0; }
  .white { background: var(--key); border: 1px solid #999; border-radius: 0 0 4px 4px; }
  .black { height: 62%; background: var(--black); border: 1px solid #000; border-radius: 0 0 3px 3px; z-index: 2; }
  .white.on { background: var(--keyon); }
  .black.on { background: var(--accent); }
  .white.demo { background: var(--yellow); }
  .black.demo { background: #c9a42a; }
  /* ghost (#2429): translucent yellow, outlined, slightly sunk; over your blue key = in time */
  .white.ghost { background: #f1e3a6; box-shadow: inset 0 0 0 2px var(--yellow); transform: translateY(2px); }
  .black.ghost { background: #6b5a1c; box-shadow: inset 0 0 0 2px var(--yellow); transform: translateY(2px); }
  .white.on.ghost { background: var(--keyon); box-shadow: inset 0 0 0 3px var(--yellow); }
  .black.on.ghost { background: var(--accent); box-shadow: inset 0 0 0 3px var(--yellow); }
  /* finger (#2431): a numbered disc in the hand's colour, low on the key where the finger lands */
  /* the octave, at the very bottom of each C: C4 is middle C (Do3 in French) */
  .octave { position: absolute; left: 0; right: 0; bottom: 2px; text-align: center; pointer-events: none;
            font: 700 clamp(8px, 1.6vw, 10px)/1 system-ui, sans-serif; color: #7a7a88; }
  .finger { position: absolute; left: 50%; bottom: max(6%, 14px); translate: -50% 0; width: min(22px, 86%); aspect-ratio: 1; border-radius: 50%;
            display: grid; place-items: center; font: 800 clamp(10px, 2.6vw, 14px)/1 system-ui, sans-serif; color: #fff;
            background: var(--hand); box-shadow: 0 0 0 2px rgba(0,0,0,.55); pointer-events: none; }
  .black .finger { bottom: 8%; box-shadow: 0 0 0 2px rgba(255,255,255,.7); }
  /* the thumb, the hand's landmark: an orange ring around its disc */
  .finger.thumb::after { content: ""; position: absolute; inset: -4px; border-radius: 50%; border: 2px solid #ff9f3f; pointer-events: none; }
  /* the five fingers are always placed: resting ones very faint, the next beats' ones faint, the due ones solid */
  .finger.rest { opacity: .26; }
  .finger.soon { opacity: .5; }
  /* a hand move coming (#2431): where the hand is (blue ring), where it goes (green), an arrow between */
  .finger.from { box-shadow: 0 0 0 2px #fff, 0 0 8px #5aa0ff; }
  .finger.to { color: #0d2a1a; box-shadow: 0 0 0 2px #0d2a1a, 0 0 10px #4fd18b; animation: pulse-to .6s ease-in-out infinite alternate; }
  @keyframes pulse-to { to { transform: scale(1.12); } }
  .move { position: absolute; top: 22%; height: 4px; z-index: 4; pointer-events: none; background: #4fd18b; border-radius: 2px;
          box-shadow: 0 0 6px #0d2a1a; }
  .move::after { content: ""; position: absolute; right: -9px; top: 50%; transform: translateY(-50%);
                 border-left: 12px solid #4fd18b; border-top: 8px solid transparent; border-bottom: 8px solid transparent; }
  .move.down::after { right: auto; left: -9px; border-left: 0; border-right: 12px solid #4fd18b; }
</style>
