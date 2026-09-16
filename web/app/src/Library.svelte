<script>
  // MIDI library browser (#2421), shared by Demo and Play: folders on the Pi, tap a file to load
  // it (parsed here on the phone), add files to the folder you're in, make folders, delete what
  // the phone added. Level = folder name (starter/beginner, …).
  import { RecordBook } from "./lib/records.js";
  import { storeKey } from "./lib/musician.svelte.js";
  import Gauge from "./Gauge.svelte";
  import { listLibrary, loadSong, uploadFile, makeFolder, removeEntry, childrenOf, crumbs, displayName, folderLabel,
           InfoCache } from "./lib/library.js";

  let { onPick, current = "" } = $props();

  const DIR_KEY = "pisynth.libraryDir";
  let entries = $state([]);
  let dir = $state(readDir());
  let busy = $state("");          // what is going on, or ""
  let error = $state("");
  let naming = $state(false);
  let folderName = $state("");
  let confirmDelete = $state("");
  let fileInput;
  const cache = new InfoCache();
  const records = new RecordBook(undefined, storeKey("pisynth.records"));  // this musician's best per song (re-read each time the sheet opens)
  let infos = $state({});          // path → info, for what's shown

  function readDir() { try { return localStorage.getItem(DIR_KEY) || ""; } catch { return ""; } }
  function setDir(d) { dir = d; confirmDelete = ""; try { localStorage.setItem(DIR_KEY, d); } catch { /* private mode */ } }

  const view = $derived(childrenOf(entries, dir));

  async function refresh() {
    error = "";
    try {
      entries = await listLibrary();
      if (dir && !entries.some(e => e.kind === "dir" && e.path === dir)) setDir("");
      const shown = {};
      for (const e of entries) { const i = cache.get(e); if (i) shown[e.path] = i; }
      infos = shown;
    } catch (err) { error = err.message; }
  }
  refresh();

  async function pick(entry) {
    busy = "loading…"; error = "";
    try {
      const { song, info } = await loadSong(entry, cache);
      infos = { ...infos, [entry.path]: info };
      onPick(song, info);
    } catch (err) { error = `${displayName(entry.path)}: ${err.message}`; }
    busy = "";
  }

  async function add(e) {
    const files = [...(e.target.files || [])];
    e.target.value = "";
    if (!files.length) return;
    error = "";
    let last = null;
    for (const f of files) {
      busy = `adding ${f.name}…`;
      try { last = await uploadFile(dir, f); } catch (err) { error = `${f.name}: ${err.message}`; }
    }
    busy = "";
    await refresh();
    const added = last && entries.find(x => x.path === last);
    if (added && files.length === 1) pick(added);             // one file: load it straight away
  }

  async function newFolder() {
    const name = folderName.trim();
    if (!name) { naming = false; return; }
    try { await makeFolder(dir ? `${dir}/${name}` : name); naming = false; folderName = ""; await refresh(); setDir(dir ? `${dir}/${name}` : name); }
    catch (err) { error = err.message; }
  }

  async function remove(entry) {
    if (confirmDelete !== entry.path) { confirmDelete = entry.path; return; }
    confirmDelete = "";
    try { await removeEntry(entry.path); await refresh(); } catch (err) { error = err.message; }
  }

  const fmt = ms => { const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const ORIGIN = { pc: "PC", phone: "phone" };
</script>

<div class="library">
  <nav class="crumbs">
    <button class="crumb" class:here={!dir} onclick={() => setDir("")}>Library</button>
    {#each crumbs(dir) as c (c.path)}
      <span class="sep">›</span><button class="crumb" class:here={c.path === dir} onclick={() => setDir(c.path)}>{folderLabel(c.name)}</button>
    {/each}
  </nav>

  <ul class="list">
    {#each view.folders as f (f.path)}
      <li>
        <button class="row" onclick={() => setDir(f.path)}>
          <svg viewBox="0 0 24 24" class="icon"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h5l2 2h8A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z" /></svg>
          <span class="name">{folderLabel(f.path)}</span>
        </button>
        {#if f.deletable}<button class="del" class:armed={confirmDelete === f.path} onclick={() => remove(f)} aria-label="delete folder">{confirmDelete === f.path ? "delete?" : "×"}</button>{/if}
      </li>
    {/each}
    {#each view.files as f (f.path)}
      <li>
        <button class="row" class:current={current === f.path} onclick={() => pick(f)}>
          <svg viewBox="0 0 24 24" class="icon note"><path d="M9 17.5a2.5 2.5 0 1 1-2-2.45V5l10-2v10.5a2.5 2.5 0 1 1-2-2.45V6.4l-6 1.2z" /></svg>
          <span class="name">{displayName(f.path)}</span>
          {#if f.score}<span class="scorebadge" title="has a score">🎼</span>{/if}
          <span class="tags">
            {#if infos[f.path]}{fmt(infos[f.path].durationMs)}{#if infos[f.path].hands >= 2} · 2 hands{/if}{/if}
            {#if infos[f.path]?.difficulty}<span class="diff"><Gauge value={infos[f.path].difficulty} /></span>{/if}
            {#if records.get(f.path)}<span class="best" title="your best on this phone">★ {records.get(f.path).score}</span>{/if}
            {#if ORIGIN[f.origin]}<span class="origin">{ORIGIN[f.origin]}</span>{/if}
          </span>
        </button>
        {#if f.deletable}<button class="del" class:armed={confirmDelete === f.path} onclick={() => remove(f)} aria-label="delete file">{confirmDelete === f.path ? "delete?" : "×"}</button>{/if}
      </li>
    {/each}
    {#if !view.folders.length && !view.files.length && !error}<li class="empty muted">{entries.length || dir ? "Empty folder." : "Loading the library…"}</li>{/if}
  </ul>

  {#if error}<p class="error">{error}</p>{/if}
  {#if busy}<p class="muted">{busy}</p>{/if}

  <div class="actions">
    <button class="small" onclick={() => fileInput.click()}>Add here</button>
    <input bind:this={fileInput} type="file" accept=".mid,.midi,audio/midi,.musicxml,.xml,.mxl" multiple hidden onchange={add}>
    {#if naming}
      <input class="fname" bind:value={folderName} placeholder="folder name" onkeydown={e => e.key === "Enter" && newFolder()}>
      <button class="small" onclick={newFolder}>OK</button>
    {:else}
      <button class="small ghost" onclick={() => (naming = true)}>New folder</button>
    {/if}
  </div>
</div>

<style>
  .library { margin-top: 2px; }
  .crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 2px; font-size: .85rem; }
  .crumb { margin: 0; padding: 4px 6px; background: none; color: var(--accent); font-weight: 500; border-radius: 6px; }
  .crumb.here { color: var(--fg); font-weight: 700; }
  .sep { color: var(--muted); }
  .list { list-style: none; max-height: min(38vh, 320px); overflow-y: auto; overscroll-behavior: contain; margin-top: 4px;
          border-radius: 8px; background: rgba(0,0,0,.18); }
  li { display: flex; align-items: center; }
  .row { flex: 1; min-width: 0; margin: 0; display: flex; align-items: center; gap: 8px; padding: 9px 10px; background: none;
         color: var(--fg); font-weight: 500; text-align: left; border-radius: 0; }
  .row.current { color: var(--yellow); }
  .icon { width: 18px; height: 18px; fill: var(--muted); flex: 0 0 auto; }
  .icon.note { fill: var(--accent); }
  .name { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tags { font-size: .72rem; color: var(--muted); white-space: nowrap; }
  .diff { margin-left: 6px; }
  .scorebadge { flex: 0 0 auto; font-size: .9rem; }
  .best { margin-left: 4px; color: var(--yellow); font-weight: 700; }
  .origin { margin-left: 4px; padding: 1px 5px; border-radius: 4px; background: #3a3a48; }
  .del { margin: 0 6px 0 0; padding: 4px 8px; background: none; color: var(--muted); font-weight: 400; }
  .del.armed { color: #ff7a7a; font-weight: 700; }
  .empty { padding: 10px; }
  .actions { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
  .small { margin: 0; padding: 6px 10px; font-size: .85rem; border-radius: 8px; }
  .ghost { background: #3a3a48; }
  .fname { font: inherit; padding: 6px 8px; border-radius: 8px; border: 1px solid #333; background: var(--bg); color: var(--fg); min-width: 0; flex: 1; }
  .error { color: #ff7a7a; margin-top: 6px; font-size: .85rem; }
</style>
