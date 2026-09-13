<script>
  // On-screen keyboard (#659). Positions come from lib/viewport.js, the same mapping the note
  // highway uses (#2418), so a `view` ({x0, span} in white keys) can slide smoothly.
  import { keysInView, rangeView, toPct } from "./lib/viewport.js";
  // on = your keys (blue) · demo = keys to light yellow · ghost = the perfect timing (#2429), drawn
  // as a translucent, outlined key that can overlap yours · fingers = Map note → {finger, color}: the
  // suggested finger, a numbered badge on the key (#2431)
  // arrows = Map note → +1 / −1: the hand moves there next (a green arrow, the new position's fingers in green)
  let { low = 36, high = 96, view = null, on = new Set(), demo = new Set(), ghost = new Set(), fingers = null, arrows = null, height = "34vh", minHeight = "150px" } = $props();

  const shown = $derived(view ?? rangeView(low, high));
  const layout = $derived(keysInView(shown).map(k => ({ ...k, ...toPct(k, shown) })));
</script>

<div class="keyboard" aria-label="live keyboard" style:height style:min-height={minHeight}>
  {#each layout as k (k.n)}
    <div class="key" class:black={k.black} class:white={!k.black} class:on={on.has(k.n)} class:demo={demo.has(k.n) && !on.has(k.n)} class:ghost={ghost.has(k.n)}
         style:left="{k.left}%" style:width="{k.width}%">
      {#if arrows?.has(k.n)}
        <span class="move" class:down={arrows.get(k.n) < 0} aria-label="move the hand {arrows.get(k.n) > 0 ? 'up' : 'down'}">
          <svg viewBox="0 0 24 24"><path d="M4 10.5h10V6l7 6-7 6v-4.5H4z" /></svg>
        </span>
      {/if}
      {#if fingers?.has(k.n)}<span class="finger" class:next={fingers.get(k.n).next} style:--hand={fingers.get(k.n).color}>{fingers.get(k.n).finger}</span>{/if}
    </div>
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
  .finger { position: absolute; left: 50%; bottom: 6%; translate: -50% 0; width: min(22px, 86%); aspect-ratio: 1; border-radius: 50%;
            display: grid; place-items: center; font: 800 clamp(10px, 2.6vw, 14px)/1 system-ui, sans-serif; color: #fff;
            background: var(--hand); box-shadow: 0 0 0 2px rgba(0,0,0,.55); pointer-events: none; }
  .black .finger { bottom: 8%; box-shadow: 0 0 0 2px rgba(255,255,255,.7); }
  /* a hand move coming (#2431): the new position's fingers in green, a green arrow pointing the way */
  .finger.next { background: #4fd18b; color: #0d2a1a; box-shadow: 0 0 0 2px #0d2a1a, 0 0 10px #4fd18b; }
  .move { position: absolute; left: 50%; bottom: 34%; translate: -50% 0; width: 26px; height: 26px; z-index: 3; pointer-events: none;
          animation: nudge .5s ease-in-out infinite alternate; }
  .black .move { bottom: 40%; }
  .move svg { width: 100%; height: 100%; fill: #4fd18b; filter: drop-shadow(0 0 3px #0d2a1a); }
  .move.down svg { transform: scaleX(-1); }
  @keyframes nudge { from { transform: translateX(-3px); } to { transform: translateX(3px); } }
</style>
