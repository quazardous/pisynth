<script>
  // On-screen keyboard (#659). Positions come from lib/viewport.js, the same mapping the note
  // highway uses (#2418), so a `view` ({x0, span} in white keys) can slide smoothly.
  import { keysInView, rangeView, toPct } from "./lib/viewport.js";
  // on = your keys (blue) · demo = keys to light yellow · ghost = the perfect timing (#2429), drawn
  // as a translucent, outlined key that can overlap yours
  let { low = 36, high = 96, view = null, on = new Set(), demo = new Set(), ghost = new Set(), height = "34vh", minHeight = "150px" } = $props();

  const shown = $derived(view ?? rangeView(low, high));
  const layout = $derived(keysInView(shown).map(k => ({ ...k, ...toPct(k, shown) })));
</script>

<div class="keyboard" aria-label="live keyboard" style:height style:min-height={minHeight}>
  {#each layout as k (k.n)}
    <div class="key" class:black={k.black} class:white={!k.black} class:on={on.has(k.n)} class:demo={demo.has(k.n) && !on.has(k.n)} class:ghost={ghost.has(k.n)}
         style:left="{k.left}%" style:width="{k.width}%"></div>
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
</style>
