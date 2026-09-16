<script>
  // Find a score (#2657): search the catalogue kept on pisynth — words in any order, without accents — with
  // categories, level, hands, composer and order; ★ favourites and recently played, per musician. Tap a score:
  // it opens in the piano view.
  import Gauge from "./Gauge.svelte";
  import { CATEGORIES, SORTS, searchCatalog, loadCatalogSong, ScoreShelf } from "./lib/catalog.js";
  import { storeKey, onMusicianChange } from "./lib/musician.svelte.js";

  let { onPick, current = "" } = $props();

  let q = $state(""), category = $state(""), composer = $state(""), level = $state(0), hands = $state(0), sort = $state("popular");
  let shelfView = $state("");                        // "" (search) | "fav" | "recent"
  let items = $state.raw([]), total = $state(0), size = $state(0), facets = $state.raw({}), busy = $state(false), error = $state("");
  let shelf = $state.raw(new ScoreShelf(globalThis.localStorage, storeKey("pisynth.scoreShelf")));
  let shelfTick = $state(0);
  onMusicianChange(() => { shelf = new ScoreShelf(globalThis.localStorage, storeKey("pisynth.scoreShelf")); });

  let seq = 0, timer = null;
  async function run(more = false) {
    const id = ++seq;
    busy = true; error = "";
    try {
      const r = await searchCatalog({ q, category, composer, level, hands, sort, offset: more ? items.length : 0 });
      if (id !== seq) return;
      items = more ? [...items, ...r.items] : r.items;
      total = r.total; size = r.size; facets = r.facets || {};
    } catch (err) { if (id === seq) error = err.message; }
    if (id === seq) busy = false;
  }
  $effect(() => {                                    // search as you type (a short pause), at once for a filter
    const typed = q;
    category; composer; level; hands; sort;
    clearTimeout(timer);
    timer = setTimeout(() => run(), typed ? 250 : 0);
    return () => clearTimeout(timer);
  });

  async function open(item) {
    busy = true; error = "";
    try {
      const song = await loadCatalogSong(item);
      shelf.played(item); shelfTick++;
      onPick(song);
    } catch (err) { error = `${item.title}: ${err.message}`; }
    busy = false;
  }

  function star(e, item) { e.stopPropagation(); shelf.toggleFav(item); shelfTick++; }

  const shown = $derived.by(() => { shelfTick; return shelfView === "fav" ? shelf.fav : shelfView === "recent" ? shelf.recent : items; });
  const composers = $derived(Object.entries(facets.composers || {}).sort((a, b) => b[1] - a[1]).slice(0, 80));
  const fmt = s => (s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}` : "");
  const narrowed = $derived(!!(q.trim() || category || composer || level || hands));
</script>

<div class="catalog">
  <div class="searchrow">
    <input class="search" type="search" bind:value={q} placeholder="Search: Chopin nocturne, Für Elise, reel…"
           oninput={() => (shelfView = "")} aria-label="search the scores">
    <button class="shelf" class:on={shelfView === "fav"} onclick={() => (shelfView = shelfView === "fav" ? "" : "fav")} aria-label="favourites">★</button>
    <button class="shelf" class:on={shelfView === "recent"} onclick={() => (shelfView = shelfView === "recent" ? "" : "recent")} aria-label="recently played">
      <svg viewBox="0 0 24 24"><path d="M13 3a9 9 0 1 0 8.95 10h-2.02A7 7 0 1 1 13 5v3l4-4-4-4zm-1 5v5.4l4.2 2.5.8-1.3-3.5-2.1V8z" /></svg>
    </button>
  </div>

  {#if !shelfView}
    <div class="chips">
      <button class:on={!category} onclick={() => (category = "")}>All</button>
      {#each CATEGORIES as [id, label] (id)}
        <button class:on={category === id} onclick={() => (category = category === id ? "" : id)}>{label}{#if facets.categories?.[id]}<small>{facets.categories[id]}</small>{/if}</button>
      {/each}
    </div>
    <div class="filters">
      <select bind:value={level} aria-label="level">
        <option value={0}>Any level</option>
        {#each [1, 2, 3, 4, 5] as l (l)}<option value={l}>Level {l}{facets.levels?.[l] ? ` (${facets.levels[l]})` : ""}</option>{/each}
      </select>
      <select bind:value={hands} aria-label="hands">
        <option value={0}>Any hands</option>
        <option value={2}>Two hands</option>
        <option value={1}>Melody</option>
      </select>
      <select bind:value={composer} aria-label="composer">
        <option value="">All composers</option>
        {#if composer && !composers.some(([c]) => c === composer)}<option value={composer}>{composer}</option>{/if}
        {#each composers as [c, n] (c)}<option value={c}>{c} ({n})</option>{/each}
      </select>
      <select bind:value={sort} aria-label="order">
        {#each SORTS as [id, label] (id)}<option value={id}>{label}</option>{/each}
      </select>
    </div>
  {/if}

  <ul class="list">
    {#each shown as item (item.id)}
      <li>
        <button class="row" class:current={current === `catalog:${item.id}`} onclick={() => open(item)}>
          <span class="main">
            <span class="name">{item.title}</span>
            <span class="by">{item.composer}{#if item.hands === 1} · melody{/if}{#if item.seconds} · {fmt(item.seconds)}{/if}</span>
          </span>
          {#if item.level}<span class="diff"><Gauge value={item.level * 2} /></span>{/if}
        </button>
        <button class="fav" class:on={(shelfTick, shelf.isFav(item.id))} onclick={e => star(e, item)} aria-label="favourite">★</button>
      </li>
    {/each}
    {#if !shown.length && !busy}
      <li class="empty muted">{shelfView === "fav" ? "No favourites yet: tap ★ on a score." : shelfView === "recent" ? "Nothing played yet." : error ? "" : size ? "No score matches." : "No score catalogue on pisynth yet."}</li>
    {/if}
  </ul>

  {#if error}<p class="error">{error}</p>{/if}
  {#if !shelfView}
    <p class="foot muted">
      {#if busy}searching…{:else if narrowed}{total} score{total === 1 ? "" : "s"}{:else if size}the {total} most played of {size} · search or filter to see them all{/if}
      {#if items.length < total && !busy}<button class="more" onclick={() => run(true)}>More</button>{/if}
    </p>
  {/if}
</div>

<style>
  .catalog { margin-top: 4px; }
  .searchrow { display: flex; gap: 6px; align-items: center; }
  .search { flex: 1; min-width: 0; font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid #3a3a48; background: var(--bg); color: var(--fg);
            -webkit-user-select: text; user-select: text; }
  .shelf { margin: 0; width: 36px; height: 36px; padding: 0; border-radius: 50%; background: #2c2c3a; color: var(--muted); display: grid; place-items: center; font-size: 1.05rem; }
  .shelf svg { width: 18px; height: 18px; fill: currentColor; }
  .shelf.on { background: var(--yellow); color: #121218; }
  .chips { display: flex; gap: 5px; overflow-x: auto; padding: 6px 0 2px; scrollbar-width: none; }
  .chips button { flex: 0 0 auto; margin: 0; padding: 5px 10px; border-radius: 999px; background: #2c2c3a; color: var(--fg); font-size: .8rem; font-weight: 600; }
  .chips button small { margin-left: 4px; color: var(--muted); font-weight: 500; }
  .chips button.on { background: var(--accent); color: #fff; }
  .chips button.on small { color: #e6eeff; }
  .filters { display: grid; grid-template-columns: repeat(auto-fit, minmax(118px, 1fr)); gap: 5px; margin-top: 5px; }
  .filters select { min-width: 0; font: inherit; font-size: .8rem; padding: 5px 6px; border-radius: 8px; border: 1px solid #3a3a48; background: var(--bg); color: var(--fg); }
  .list { list-style: none; max-height: min(34vh, 300px); overflow-y: auto; overscroll-behavior: contain; margin-top: 6px;
          border-radius: 8px; background: rgba(0,0,0,.18); }
  li { display: flex; align-items: center; }
  .row { flex: 1; min-width: 0; margin: 0; display: flex; align-items: center; gap: 8px; padding: 7px 10px; background: none;
         color: var(--fg); text-align: left; border-radius: 0; font-weight: 500; }
  .row.current .name { color: var(--yellow); }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .name, .by { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .by { font-size: .72rem; color: var(--muted); }
  .fav { margin: 0 6px 0 0; padding: 4px 8px; background: none; color: #4a4a58; font-size: 1.05rem; }
  .fav.on { color: var(--yellow); }
  .empty { padding: 10px; }
  .foot { display: flex; align-items: center; gap: 8px; margin-top: 6px; font-size: .75rem; }
  .more { margin: 0 0 0 auto; padding: 4px 10px; font-size: .8rem; border-radius: 8px; background: #3a3a48; }
  .error { color: #ff7a7a; margin-top: 6px; font-size: .85rem; }
</style>
