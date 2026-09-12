<script>
  import { isBlack } from "./lib/theory.js";
  let { low = 36, high = 96, on = new Set() } = $props();

  const layout = $derived.by(() => {
    const whites = [];
    for (let n = low; n <= high; n++) if (!isBlack(n)) whites.push(n);
    const w = 100 / whites.length;
    const keys = [];
    let wi = 0;
    for (let n = low; n <= high; n++) {
      if (isBlack(n)) keys.push({ n, black: true, left: wi * w - w * 0.3, width: w * 0.6 });
      else keys.push({ n, black: false, left: wi++ * w, width: w });
    }
    return keys;
  });
</script>

<div class="keyboard" aria-label="live keyboard">
  {#each layout as k (k.n)}
    <div class="key" class:black={k.black} class:white={!k.black} class:on={on.has(k.n)}
         style:left="{k.left}%" style:width="{k.width}%"></div>
  {/each}
</div>

<style>
  .keyboard { position: relative; height: 34vh; min-height: 150px; background: var(--black); border-top: 2px solid #000; }
  .key { position: absolute; top: 0; bottom: 0; }
  .white { background: var(--key); border: 1px solid #999; border-radius: 0 0 4px 4px; }
  .black { height: 62%; background: var(--black); border: 1px solid #000; border-radius: 0 0 3px 3px; z-index: 2; }
  .white.on { background: var(--keyon); }
  .black.on { background: var(--accent); }
</style>
