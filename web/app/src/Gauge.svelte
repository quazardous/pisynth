<script>
  // A song's difficulty (#2436) as a 5-segment gauge, green to red, the way games show it; the exact
  // value (1–10) is in the tooltip, or beside it with `number`.
  import { gaugeLevel } from "./lib/difficulty.js";

  let { value, number = false } = $props();
  const COLORS = ["#4fd18b", "#a6d84f", "#ffd23f", "#ff9f3f", "#ff5a5a"];
  const lit = $derived(gaugeLevel(value));
</script>

<span class="gauge" title="difficulty {value.toFixed(1)} / 10" aria-label="difficulty {lit} of 5" style:--c={COLORS[lit - 1]}>
  {#each COLORS as _, k (k)}<i class:on={k < lit} style:height="{40 + k * 15}%"></i>{/each}
  {#if number}<small>{value.toFixed(1)}</small>{/if}
</span>

<style>
  .gauge { display: inline-flex; align-items: flex-end; gap: 2px; height: .9em; vertical-align: -1px; }
  i { width: 4px; border-radius: 1px; background: rgba(160,160,180,.28); }
  i.on { background: var(--c); }
  small { margin-left: 4px; align-self: center; color: var(--c); font-weight: 700; font-size: .85em; }
</style>
