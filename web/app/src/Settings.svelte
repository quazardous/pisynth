<script>
  // Settings panel behind the cog (#2419): Sound (#2417), Metronome (#2658), Display, Musicians, Latency (#659) and About. It opens over
  // the player, which keeps playing underneath — change the reverb while pisynth plays a song.
  import Sound from "./Sound.svelte";
  import Metronome from "./Metronome.svelte";
  import Latency from "./Latency.svelte";
  import { prefs, setNotation, setArcade } from "./lib/prefs.svelte.js";
  import { aids, setAid } from "./lib/aids.svelte.js";
  import { noteName } from "./lib/theory.js";
  import { musicians, selectMusician, renameMusician, recolorMusician, currentMusician } from "./lib/musician.svelte.js";
  import { musicianKey } from "./lib/musicians.js";
  import { Progress } from "./lib/progress.js";

  let { panel, onPanel, onClose, onFrame, onMessage, send } = $props();
  const HELP = [
    ["fingers", "Finger numbers", "A suggested finger on each note and on the keys: 1 = thumb … 5 = little finger. Worked out from the usual rules; a teacher may choose otherwise."],
    ["moves", "Hand moves", "When the hand has to move to a new position: a green arrow on the keyboard and the new position's fingers in green, right after the key before the move."],
    ["ghost", "Ghost keys", "In \"I play\", the keyboard shows the perfect timing next to your playing: in time, your blue key gets a yellow outline."],
    ["shake", "Shaking notes", "A note shakes harder and harder as it reaches the yellow line, so you feel the moment coming."],
  ];
  const TABS = [["sound", "Sound"], ["metronome", "Metronome"], ["display", "Display"], ["musicians", "Musicians"], ["latency", "Latency"], ["about", "About"]];

  let build = $state("…");
  let confirmUnpair = $state(false);
  let unpairError = $state("");

  $effect(() => {
    if (panel !== "about") return;
    fetch("/build.json", { cache: "no-store" })
      .then(r => (r.ok ? r.json() : { hash: "dev" }))
      .then(b => (build = b.hash || "dev"))
      .catch(() => (build = "dev"));
  });

  async function unpair() {
    if (!confirmUnpair) { confirmUnpair = true; return; }
    try {
      const r = await fetch("/api/unpair", { method: "POST", credentials: "same-origin" });
      if (!r.ok && r.status !== 401) throw new Error(`${r.status}`);
      location.replace("/");                                   // back to the pairing screen
    } catch (err) { unpairError = err.message; confirmUnpair = false; }
  }
</script>

<div class="panel" role="dialog" aria-label="settings">
  <div class="top">
    <button class="back" onclick={onClose} aria-label="close settings">
      <svg viewBox="0 0 24 24"><path d="M15.5 4.5 8 12l7.5 7.5" /></svg>
    </button>
    <span class="title">Settings</span>
  </div>
  <div class="tabs">
    {#each TABS.filter(([id]) => id !== "metronome" || prefs.view === "piano") as [id, label] (id)}
      <button class:on={panel === id} onclick={() => onPanel(id)}>{label}</button>
    {/each}
  </div>

  <div class="body">
    {#if panel === "sound"}
      <Sound {onMessage} {send} />
    {:else if panel === "metronome"}
      <Metronome />
    {:else if panel === "display"}
      <section class="card">
        <h1>Note names</h1>
        <p class="muted">Used on the falling notes, the live chord and everywhere a note is named.</p>
        {#each [["en", "English — C D E F G A B"], ["fr", "French — Do Ré Mi Fa Sol La Si"]] as [id, label] (id)}
          <label class="choice">
            <input type="radio" name="notation" checked={prefs.notation === id} onchange={() => setNotation(id)}>
            <span>{label}<br><small class="muted">middle C = {noteName(60, id)}</small></span>
          </label>
        {/each}
      </section>
      <section class="card">
        <h1>Help for {currentMusician().name}</h1>
        <p class="muted">Each musician keeps their own: a beginner keeps them all, someone more at ease turns some off.</p>
        {#each HELP as [id, label, text] (id)}
          <label class="choice">
            <input type="checkbox" checked={aids[id]} onchange={e => setAid(id, e.target.checked)}>
            <span>{label}<br><small class="muted">{text}</small></span>
          </label>
        {/each}
      </section>
      <section class="card">
        <h1>Effects</h1>
        <label class="choice">
          <input type="checkbox" checked={prefs.arcade} onchange={e => setArcade(e.target.checked)}>
          <span>Arcade effects<br><small class="muted">Explosions on your hits, combos announced with their sounds, a
            racing score. Turn off for calmer practice.</small></span>
        </label>
      </section>
    {:else if panel === "musicians"}
      <section class="card">
        <h1>Musicians</h1>
        <p class="muted">Each musician has their own level, XP, records and help options on this phone. Tap a name to rename
          it, the dot to change its colour; choose who plays here or with the menu at the top.</p>
        {#each musicians.list as m (m.id)}
          <div class="musician" class:on={musicians.current === m.id}>
            <input type="radio" name="musician" checked={musicians.current === m.id} onchange={() => selectMusician(m.id)} aria-label="play as {m.name}">
            <button class="mcolor" style:background={m.color} onclick={() => recolorMusician(m.id)} aria-label="{m.name}'s colour — tap for the next one"></button>
            <input class="mname" value={m.name} maxlength="24" onchange={e => { renameMusician(m.id, e.target.value); e.target.value = musicians.list.find(x => x.id === m.id).name; }}>
            <span class="mlevel">Lv {new Progress(undefined, musicianKey("pisynth.progress", m.id)).level.level}</span>
          </div>
        {/each}
      </section>
    {:else if panel === "latency"}
      <Latency {onFrame} />
    {:else}
      <section class="card">
        <h1>pisynth companion</h1>
        <p class="muted">Build <code>{build}</code></p>
        <p>This browser is paired with pisynth. Only one browser can be paired at a time; pairing another one
          (QR icon on the pisynth screen) disconnects this one.</p>
        <button class="danger" onclick={unpair}>{confirmUnpair ? "Tap again to unpair" : "Unpair this browser"}</button>
        {#if unpairError}<p class="error">Couldn't unpair: {unpairError}</p>{/if}
      </section>
    {/if}
  </div>
</div>

<style>
  .panel { position: fixed; inset: 0; z-index: 50; background: var(--bg); display: flex; flex-direction: column;
           padding-top: env(safe-area-inset-top, 0); }
  .top { display: flex; align-items: center; gap: 6px; min-height: 48px; padding: 0 8px; background: var(--bar); }
  .back { margin: 0; padding: 8px; background: none; display: grid; place-items: center; }
  .back svg { width: 24px; height: 24px; fill: none; stroke: var(--fg); stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
  .title { font-weight: 700; }
  .tabs { display: flex; gap: 4px; padding: 6px 12px; background: var(--bar); border-top: 1px solid #2c2c3a; overflow-x: auto; }
  .tabs button { flex: 0 0 auto; }
  .tabs button { margin: 0; padding: 6px 14px; border-radius: 999px; background: none; color: var(--muted); font-size: .9rem; font-weight: 600; }
  .tabs button.on { background: #2c2c3a; color: var(--fg); }
  .body { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow-y: auto; }
  .danger { background: #a33; }
  .choice { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
  .choice input { width: 22px; height: 22px; flex: 0 0 auto; }
  .musician { display: flex; align-items: center; gap: 10px; margin-top: 10px; padding: 6px 8px; border-radius: 10px; }
  .musician.on { background: rgba(195,139,255,.14); }
  .mcolor { margin: 0; padding: 0; width: 26px; height: 26px; flex: 0 0 auto; border-radius: 50%; box-shadow: 0 0 0 2px #121218, 0 0 0 3px #3a3a48; }
  .musician input[type=radio] { width: 22px; height: 22px; flex: 0 0 auto; }
  .mname { flex: 1; min-width: 0; font: inherit; font-weight: 600; padding: 8px 10px; border-radius: 8px; border: 1px solid #3a3a48;
           background: #17171f; color: var(--fg); -webkit-user-select: text; user-select: text; }
  .mlevel { color: #c38bff; font-weight: 800; font-size: .85rem; }
  .error { color: #ff7a7a; margin-top: 8px; }
  code { font-size: .85em; }
</style>
