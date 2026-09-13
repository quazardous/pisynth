<script>
  // The companion's main screen (#2419): one player, two modes, same design.
  //  - "I play" (#2418): notes fall onto the keyboard, you play them, the phone judges each press
  //    on the Pi's own timestamps (lib/clock.js + lib/judge.js). The phone ticks the count-in itself.
  //  - "Listen" (#2416): pisynth plays the song (lib/demo.js streams it), the same notes fall and
  //    light up as the synth sounds them.
  // Tempo, A–B loop and position are shared, so you can listen to a passage then play it.
  // With no song loaded the screen is the live keyboard + chord name (the old Live tab, #659).
  import { onDestroy, untrack } from "svelte";
  import { decodeFrame, NoteState } from "./lib/midi.js";
  import { sampleSong } from "./lib/midifile.js";
  import { songNotes, noteRange, noteTracks, visibleNotes, longestNote, timeToY } from "./lib/highway.js";
  import { planView, FollowView, keyRect, toPct } from "./lib/viewport.js";
  import { Judge } from "./lib/judge.js";
  import { ghostKeys, ghostPulses, sameSet, GHOST_MIN_MS } from "./lib/ghost.js";
  import { fingering, keyFingers, fingersKey, handShifts, upcomingShifts, handPositions } from "./lib/fingering.js";
  import { ClockSync } from "./lib/clock.js";
  import { DemoSender } from "./lib/demo.js";
  import { countInTimes, scheduleCountdown } from "./lib/click.js";
  import { ComboTracker, ParticlePool, RollingNumber } from "./lib/arcade.js";
  import { comboSting, comboBreaker, oops, fuseTick, restartCue, retryBuzz } from "./lib/sfx.js";
  import { comboSplash, oopsSplash, levelUpSplash, unlockSplash } from "./lib/comic.js";
  import { songFeatures, difficulty } from "./lib/difficulty.js";
  import { Progress, levelDifficulty } from "./lib/progress.js";
  import { detectChord, noteName, pitchName } from "./lib/theory.js";
  import { prefs, setPlayMode, PLAY_MODES } from "./lib/prefs.svelte.js";
  import { aids } from "./lib/aids.svelte.js";
  import { RecordBook, songKey } from "./lib/records.js";
  import { EndlessScore } from "./lib/endless.js";
  import { songParts, partAt, partState, PartBook } from "./lib/parts.js";
  import { musicians, storeKey } from "./lib/musician.svelte.js";
  import { enterPlayMode, exitPlayMode, releaseAwake } from "./lib/screen.js";
  import Keyboard from "./Keyboard.svelte";
  import Library from "./Library.svelte";
  import { listLibrary, loadSong, nextSongEntry, displayName } from "./lib/library.js";
  import Comic from "./Comic.svelte";
  import Gauge from "./Gauge.svelte";

  let { onFrame, onMessage, send, mode = "play", onMode = () => {} } = $props();

  const AHEAD_MS = 2600;           // song ms visible above the line: at 50 % tempo the notes fall half as fast
  const PAST_MS = 300;             // a note stays drawn this long after it ends
  const FOLLOW_AHEAD_MS = 2000;    // the sliding window looks this far ahead
  const COUNT_IN = 3;               // "3 · 2 · 1 · GO!" (video-game count-in, played by the phone)
  let countBeats = COUNT_IN;         // this run's count-in (one beat between infinite laps)
  const START_BEATS = 3;            // stopped: the keyboard shows the fingers of this many beats from the start
  const SHAKE_BEATS = 1;            // "I play": a note starts shaking this many beats before the line
  const TRACK_COLORS = ["#5aa0ff", "#4fd18b", "#c38bff", "#ff9f5a"];
  const EMPTY = { events: [], durationMs: 0, name: "" };

  let song = $state.raw(null);
  let error = $state("");
  let status = $state("");
  let tempo = $state(100);
  let playing = $state(false);
  let position = $state(0);        // song ms shown on the bar
  let loop = $state(null);         // {a, b} song ms
  let sheet = $state(null);         // null | "library" (📁 button) | "options" (⋯: tempo, loop)
  let finished = $state(false);
  let best = $state.raw(null);      // this song's record on the phone, and what the last run beat
  let countIn = $state(0);
  let stats = $state({ score: 0, streak: 0, accuracy: 0 });
  let flash = $state(null);        // {kind, delta, id}
  let liveOn = $state(new Set());
  let guide = $state(new Set());
  let ghost = $state(new Set());                    // "I play": the perfect timing, on the keyboard (#2429)
  const GHOST_PULSE_MS = 220;
  let view = $state({ x0: 0, span: 15 });
  let stageW = $state(0), stageH = $state(0);
  let canvas = $state(null);

  const current = $derived(song ?? EMPTY);
  const notes = $derived(songNotes(current.events, current.durationMs).map((n, i) => ({ ...n, i })));
  const maxLen = $derived(longestNote(notes));
  const range = $derived(noteRange(notes));
  const hands = $derived(noteTracks(notes));
  const plan = $derived(song && stageW ? planView(range.low, range.high, stageW) : null);
  const sounding = $derived([...liveOn].sort((a, b) => a - b));
  const fingers = $derived(fingering(notes));                // suggested finger per note, worked out once per song (#2431)
  const features = $derived(songFeatures(notes, fingers));
  const songDiff = $derived(difficulty(features));             // how hard the song is (#2436); the tempo weighs on XP
  let progress = new Progress(undefined, storeKey("pisynth.progress"));   // XP and level of the musician playing
  let lv = $state.raw(progress.level), xpGain = $state.raw(null), levelUp = $state.raw(null), runActive = false;
  const handColor = track => TRACK_COLORS[Math.max(0, hands.indexOf(track)) % TRACK_COLORS.length];
  const shifts = $derived(handShifts(notes, fingers));         // where a hand has to move to a new position
  let keyFing = $state.raw(new Map()), keyFingSig = "";      // fingers shown on the keyboard: {note → {finger, color, move}}
  let keyMoves = $state.raw([]);                             // hand moves on the keyboard: [{from: [notes], to: [notes], dir}]

  // The keyboard shows where each finger goes: the keys due within `aheadMs` (song ms) of `t`. Playing, a hand
  // about to move shows both, right after the key before the move: where it is (blue) and where it goes (green),
  // with an arrow from one to the other.
  // `dueMs`: notes held or starting within it are shown in full; the later ones (up to `aheadMs`) faintly, so
  // the hand can get ready.
  function showFingers(t, aheadMs, withMoves = false, dueMs = aheadMs) {
    const m = keyFingers(notes, fingers, t, aheadMs, maxLen);
    const hand5 = handPositions(notes, fingers, shifts, t, 4 * beatMs());   // the five fingers of each hand, always
    const moves = withMoves ? upcomingShifts(notes, fingers, shifts, t, 3 * beatMs(), beatMs()) : [];
    const faint = f => f.start > t + dueMs;
    const sig = `${fingersKey(hand5)}|${[...m].map(([n, f]) => `${n}:${f.finger}${faint(f) ? "~" : ""}`).join(",")}|${moves.map(mv => `${fingersKey(mv.from)}>${fingersKey(mv.to)}`).join(";")}`;
    if (sig === keyFingSig) return;
    keyFingSig = sig;
    const shown = new Map([...hand5].map(([n, f]) => [n, { finger: f.finger, color: handColor(f.track), move: "rest" }]));
    for (const [n, f] of m) shown.set(n, { finger: f.finger, color: handColor(f.track), move: faint(f) ? "soon" : "" });
    for (const mv of moves) {
      for (const [n, f] of mv.from) shown.set(n, { finger: f.finger, color: "#5aa0ff", move: "from" });
      for (const [n, f] of mv.to) shown.set(n, { finger: f.finger, color: "#4fd18b", move: "to" });
    }
    keyFing = shown;
    keyMoves = moves.map(mv => ({ from: [...mv.from.keys()], to: [...mv.to.keys()], dir: mv.dir }));
  }
  // Stopped: the hand position to start from — the first beats from where Play will start. Tap the keys
  // to find your place before playing (#2431): they light up in their lane, green where a song note starts.
  const startAt = $derived(loop?.a ?? (position >= current.durationMs ? 0 : position));
  $effect(() => { if (!playing) { notes; fingers; startAt; untrack(() => showFingers(startAt, START_BEATS * beatMs())); } });

  let judge = $state.raw(new Judge([]));             // (raw: its counters are read, not tracked)
  const clock = new ClockSync();
  const held = new NoteState();
  let follow = null, effects = [], origin = 0, clockStart = 0, from = 0, cancelClicks = () => {};
  const CLICK_LEAD_MS = 120;         // headroom to schedule the first count-in tick
  let sender = null, leadMs = 150;
  let simulated = false;             // pisynth-web says its keyboard is the dev simulator (#2434)
  let raf = 0, timer = 0, lastPaint = 0, flashId = 0;

  $effect(() => {                                   // a new song: fresh judge, back to the start
    const n = notes;
    untrack(() => { judge = new Judge(n, { tempo: tempo / 100, beatMs: beatMs() }); position = 0; loop = null; finished = false; });
  });
  $effect(() => {                                   // song or screen width changed: re-plan the view
    const p = plan, first = notes.slice(0, 8).map(n => n.note);
    if (!p) return;
    untrack(() => {
      follow = p.mode === "follow" ? new FollowView(p) : null;
      if (follow) { follow.aim([], first); follow.jump(follow.target); }
      view = follow ? { x0: follow.x0, span: follow.span } : { x0: p.x0, span: p.span };
      paint();
    });
  });
  $effect(() => { mode; untrack(() => { if (playing) stop(); finished = false; flash = null; paint(); }); });   // switching keeps the position
  $effect(() => {                                   // another musician: stop, and their own level, records, infinite bests
    musicians.current;
    untrack(() => {
      if (playing) stop();
      progress = new Progress(undefined, storeKey("pisynth.progress"));
      endlessBook = new EndlessScore(undefined, storeKey("pisynth.endless"));
      partBook = new PartBook(undefined, storeKey("pisynth.parts"));
      lv = progress.level; xpGain = null; best = null; finished = false; endlessShown = 0; laps = 0;
    });
  });

  const tf = () => tempo / 100;
  const songPos = now => origin + (now - clockStart) * tf();
  const ghostTime = now => songPos(now - clock.typicalLag());   // song time a press arriving now was played at
  const beatMs = () => 60000 / (current.bpm || 100);         // song ms per beat

  $effect(() => {
    const offF = onFrame(buf => {
      if (buf === null) { held.clear(); liveOn = new Set(); return; }
      const now = performance.now();
      const ev = decodeFrame(buf);
      if (!ev) return;
      clock.observe(ev.t, now);
      if (ev.type === "on" && playing && mode === "play") {
        const at = clock.toLocal(ev.t) ?? now;
        const t = songPos(at);
        if (t >= from - 400) show(judge.press(ev.note, t), now);
      }
      if (held.apply(ev)) liveOn = new Set(held.sounding());
    });
    const offM = onMessage(msg => {
      if (msg.t === "hello") { simulated = !!msg.sim; return; }
      if (msg.t !== "demo") return;
      if (msg.state === "error" && mode === "listen") { error = "pisynth: " + msg.error; stop(false); }   // nothing to hear without the synth
      if (msg.state === "playing" && msg.lead_ms) leadMs = msg.lead_ms;
      if (msg.state === "stopped" && msg.by === "pisynth" && playing && mode === "listen") { stop(false); status = "stopped on pisynth"; }
    });
    return () => { offF(); offM(); };
  });

  // ---- play modes (⋯ or the mode button): normal · hybrid (part by part) · infinite (loops, own score) ----
  const endless = $derived(prefs.playMode === "infinite");
  const hybrid = $derived(prefs.playMode === "hybrid" && mode === "play");
  const MODE_LABEL = { normal: "Normal", hybrid: "Hybrid", infinite: "Infinite" };
  function chooseMode(m) {
    if (playing) stop();
    setPlayMode(m);
    endlessBook.reset(); endlessShown = 0; laps = 0; lastJudged = judge.score;
    loop = null;                                           // (hybrid's parts drive the loop; leaving it frees it)
    paint();
  }
  const cycleMode = () => chooseMode(PLAY_MODES[(PLAY_MODES.indexOf(prefs.playMode) + 1) % PLAY_MODES.length]);

  let endlessBook = $state.raw(new EndlessScore(undefined, storeKey("pisynth.endless")));   // (raw: swapped per musician)
  let endlessShown = $state(0), laps = $state(0), lastJudged = 0;

  // Hybrid: a part must go by without a wrong key or a missed note to unlock the next one.
  const parts = $derived(song ? songParts(current, notes) : []);
  let partBook = $state.raw(new PartBook(undefined, storeKey("pisynth.parts")));
  let partIdx = $state(0), partFails = $state(0), cleared = $state(0);
  const BOMB_FROM = 5;                                       // the bomb shows for the last strikes of a clean part
  let bomb = $state(0), finishAtEnd = false, quietLead = $state(false), retryAt = 0;
  const RETRY_PAUSE_MS = 900;                                // a missed part: its purple count shows this long before going back
  $effect(() => { song; partBook; untrack(() => { cleared = partBook.cleared(songKey(song)); partIdx = Math.min(cleared, Math.max(0, parts.length - 1)); }); });

  // Hybrid: called once every note of the part is judged (right after its last strike, not at the next bar,
  // so what's played past it belongs to the next part).
  function partDone() {
    const key = songKey(song);
    bomb = 0;
    if (partFails === 0) {
      partBook.clear(key, partIdx + 1);
      cleared = partBook.cleared(key);
      const last = partIdx + 1 >= parts.length;
      levelUp = { splash: last ? { ...unlockSplash(seed(), 0), word: "CLEARED!", caption: "the whole song" } : unlockSplash(seed(), partIdx + 2),
                  id: ++announceId };                           // (the big bubble, reused)
      comboSting(5);
      if (partIdx + 1 >= parts.length) { finishAtEnd = true; return; }   // the last part: let the song ring to its end
      partIdx++;
      loop = { a: parts[partIdx].a, b: parts[partIdx].b };
      partFails = 0;
      return;
    }
    // Missed: the purple count stays up a moment (so a going back never comes without it), then back we go.
    announce = { text: "TRY AGAIN", color: "#ff5a5a", breaker: true, splash: comboSplash(seed(), { breaker: true }), pos: splashPos(), id: ++announceId };
    if (!prefs.arcade) status = `${parts[partIdx].label}: again, without a wrong key or a missed note`;
    retryAt = performance.now() + RETRY_PAUSE_MS;
  }
  function retryPart() {
    retryAt = 0;
    retryBuzz();                                             // bzz bzz: the part again
    stop(false);
    start(parts[partIdx].a, true, true);                     // a bar to put the hand back, then a discreet cue
  }
  function restartParts() {
    partBook.forget(songKey(song)); cleared = 0; partIdx = 0;
    if (playing) stop();
    position = parts[0]?.a ?? 0; paint();
  }
  function scoreEndless(kind, tempoNow) {
    endlessBook.apply(kind, kind === "wrong" || kind === "miss" ? 0 : judge.score - lastJudged, tempoNow);
    lastJudged = judge.score;
    endlessShown = endlessBook.score;
  }

  function show(r, now) {
    if (endless && mode === "play") scoreEndless(r.kind, tf());
    if (hybrid && r.kind === "wrong") partFails++;
    effects.push({ ...r, at: now });
    flash = { kind: r.kind, delta: r.delta, id: ++flashId };
    stats = { score: judge.score, streak: judge.streak, accuracy: judge.accuracy() };
    rolling.set(judge.score);
    if (prefs.arcade) arcade(r.kind, r.note, now, r.penalty);
  }

  // ---- arcade layer (#2434): sparks, combos, announcer, racing score ----
  const combo = new ComboTracker(), sparks = new ParticlePool(300), rolling = new RollingNumber(0);
  let shownScore = $state(0), hitsShown = $state(0), announce = $state(null), announceId = 0, shakeUntil = 0;
  let oopsAt = $state(null);                                // {splash, x (% of the stage), id}: a wrong key
  const seed = () => Math.floor(Math.random() * 2 ** 32);  // every splash its own shape
  // Where a combo splash lands: high in the lanes, never twice in the same place (x: % off centre, y: % from the top).
  const splashPos = () => ({ x: Math.round((Math.random() - 0.5) * 30), y: Math.round(8 + Math.random() * 16) });

  function laneAt(note) {                                     // canvas px of a lane's centre on the line
    const dpr = globalThis.devicePixelRatio || 1;
    const v = follow ? { x0: follow.x0, span: follow.span } : view;
    const p = toPct(keyRect(note), v);
    return [((p.left + p.width / 2) / 100) * stageW * dpr, stageH * dpr - 3 * dpr, dpr];
  }

  function arcade(kind, note, now, penalty = 0) {
    const [x, y, dpr] = laneAt(note);
    if (kind === "perfect") {
      sparks.burst(x, y, { count: 18, color: "#ffd23f", speed: 420 * dpr, size: 3 * dpr });
      sparks.burst(x, y, { count: 8, color: "#ffffff", speed: 560 * dpr, size: 2 * dpr, life: 380 });
    } else if (kind === "good") sparks.burst(x, y, { count: 10, color: "#4fd18b", speed: 320 * dpr, size: 3 * dpr });
    else if (kind === "early" || kind === "late") sparks.burst(x, y, { count: 6, color: "#ff9f5a", speed: 240 * dpr, size: 2.5 * dpr });
    else if (kind === "wrong") {
      sparks.burst(x, y, { count: 8, color: "#ff5a5a", speed: 200 * dpr, spread: 0.6, size: 2.5 * dpr });
      oopsAt = { splash: oopsSplash(seed(), penalty), x: Math.min(82, Math.max(18, (x / dpr / (stageW || 1)) * 100)), id: ++announceId };
      oops();
    }
    else if (kind === "miss") sparks.burst(x, y, { count: 6, color: "#6a6a78", speed: 140 * dpr, up: false, size: 3 * dpr, life: 500 });
    const res = combo.onResult(kind);
    hitsShown = res.hits;
    if (res.announce) {
      announce = { ...res.announce, splash: comboSplash(seed(), { color: res.announce.color }), pos: splashPos(), id: ++announceId };
      comboSting(res.announce.tier);
      if (res.announce.tier >= 1) shakeUntil = now + 140;
    } else if (res.broke) {
      announce = { text: "C-C-C-COMBO BREAKER", color: "#ff5a5a", breaker: true, splash: comboSplash(seed(), { breaker: true }), pos: splashPos(), id: ++announceId };
      comboBreaker();
      shakeUntil = now + 200;
    }
  }

  function load(s) {
    stop();
    song = s; error = ""; status = ""; sheet = null;
  }

  // `lap`: infinite mode starting the song over by itself — a one-beat count-in, the infinite score goes on.
  // `quiet`: hybrid starting a part again — a whole bar to put the hand back, no count-in, a discreet cue.
  function start(at = null, lap = false, quiet = false) {
    if (!notes.length) return;
    countBeats = quiet ? 4 : lap ? 1 : COUNT_IN;
    quietLead = quiet; finishAtEnd = false; bomb = 0; retryAt = 0;
    if (!lap) { endlessBook.reset(); endlessShown = 0; laps = 0; }
    if (hybrid && parts.length) {                            // hybrid: play the part asked for, if it's unlocked
      if (!lap) partIdx = Math.min(partAt(parts, at ?? (position >= current.durationMs ? 0 : position)), cleared, parts.length - 1);
      loop = { a: parts[partIdx].a, b: parts[partIdx].b };
      at = parts[partIdx].a;
      partFails = 0;
    }
    from = at ?? loop?.a ?? (position >= current.durationMs ? 0 : position);
    const now = performance.now();
    origin = from;
    effects = []; finished = false; flash = null; error = ""; status = "";
    if (mode === "listen") {
      sender = new DemoSender({ events: current.events, send });
      sender.start(from, tf());
      clockStart = now + leadMs;                              // the Pi anchors the song this far ahead
    } else {
      const beatReal = beatMs() / tf();
      // The song reaches `from` after the count-in — and never before its first notes have fallen the whole
      // height of the lanes, so they come in from the top (a restart doesn't find them already at the line).
      const leadSong = Math.max(countBeats * beatMs(), AHEAD_MS);
      clockStart = now + CLICK_LEAD_MS + leadSong / tf();
      judge.setTempo(tf());
      judge.reset(from);
      runActive = true;                                       // this run will earn XP when it ends (#2436)
      lastJudged = 0;
      stats = { score: 0, streak: 0, accuracy: 0 };
      combo.reset(); rolling.jump(0); shownScore = 0; hitsShown = 0; announce = null; oopsAt = null; sparks.items = [];
      if (quiet) {                                            // the cue as the part starts again
        const id = setTimeout(restartCue, Math.max(0, clockStart - performance.now() - 60));
        cancelClicks = () => clearTimeout(id);
      } else cancelClicks = scheduleCountdown(countInTimes(clockStart, beatReal, countBeats), clockStart);   // from the phone
      if (simulated) {                                        // dev stack: the simulated keyboard plays along (#2434)
        const end = hybrid ? Infinity : loop?.b ?? Infinity;       // (hybrid goes on past the part when it's unlocked)
        const part = notes.filter(n => n.start >= from && n.start < end).slice(0, 5000)
          .map(n => [Math.round((n.start - from) / tf()), Math.round((Math.min(n.end, end) - from) / tf()), n.note]);
        send({ t: "sim", notes: part, in_ms: Math.round(clockStart - performance.now()) });
        status = "simulator playing along";
      }
    }
    playing = true;
    enterPlayMode();
    timer = setInterval(() => {
      sender?.tick();                                         // listen: next look-ahead batch
      if (performance.now() - lastPaint > 120) paint();       // rAF pauses when the page isn't painted
    }, 120);
    const loopFn = () => { if (!playing) return; paint(); raf = requestAnimationFrame(loopFn); };
    raf = requestAnimationFrame(loopFn);
  }

  function stop(tell = true) {
    if (!playing) return;
    clearInterval(timer); cancelAnimationFrame(raf);
    position = Math.max(from, Math.min(songPos(performance.now()), current.durationMs));
    if (sender) { if (tell) sender.stop(); else sender.playing = false; sender = null; }
    cancelClicks(); cancelClicks = () => {};
    if (simulated && mode === "play") send({ t: "sim_stop" });
    if (runActive) { runActive = false; if (judge.score > 0) awardXp(); else xpGain = null; }   // stopped, finished or looped: no points, no XP
    if (endless && mode === "play") endlessBook.save(songKey(song));   // infinite: the best score this song reached
    playing = false; countIn = 0; guide = new Set(); ghost = new Set();
    rolling.jump(judge.score); shownScore = judge.score;
    releaseAwake();
    paint();
  }

  function awardXp() {
    const r = progress.award(songKey(song), judge.counts, songDiff, tempo / 100);
    lv = r.after;
    xpGain = r.xp > 0 ? { ...r, diff: songDiff, tempo, id: ++announceId } : null;
    if (r.levelUp) {
      levelUp = { splash: levelUpSplash(seed(), r.after.level), id: ++announceId };
      comboSting(7);
    }
  }

  function finish() {
    const judged = mode === "play";
    stop();
    position = judged ? current.durationMs : 0;
    finished = judged;
    if (judged && origin === 0) {                             // a whole run, from the start: file it
      best = new RecordBook(undefined, storeKey("pisynth.records")).submit(songKey(song), { score: judge.score, accuracy: judge.accuracy(), maxHits: combo.maxHits, tempo });
    } else best = null;
    if (judged) findNext();
  }

  // The results card offers the next song of the library: the next file in the folder, or the next level.
  let nextUp = $state.raw(null);
  async function findNext() {
    nextUp = null;
    const path = song?.path;
    if (!path) return;
    try {
      const entry = nextSongEntry(await listLibrary(), path);
      if (song?.path === path) nextUp = entry;
    } catch { /* pisynth unreachable: no Next */ }
  }
  async function playNext() {
    const entry = nextUp;
    if (!entry) return;
    nextUp = null; status = "loading…";
    try { load((await loadSong(entry)).song); }
    catch (err) { status = ""; error = `${displayName(entry.path)}: ${err.message}`; }
  }

  // ↻: stop, and back to the start (or A with a loop) with a clean score — Play starts again from there.
  // (hybrid: a double tap goes back to the first part — the parts already unlocked stay unlocked)
  let lastRewind = 0;
  function rewind() {
    const now = performance.now(), double = now - lastRewind < 450;
    lastRewind = now;
    stop();
    finished = false; sheet = null; flash = null; announce = null; oopsAt = null;
    if (hybrid && double && parts.length) { partIdx = 0; loop = { a: parts[0].a, b: parts[0].b }; }
    position = loop?.a ?? 0;
    judge.reset(position);
    stats = { score: 0, streak: 0, accuracy: 0 };
    combo.reset(); rolling.jump(0); shownScore = 0; hitsShown = 0;
    endlessBook.reset(); endlessShown = 0; laps = 0; lastJudged = 0;
    paint();
  }

  function seek(e) {
    const to = Number(e.target.value);
    if (playing) { stop(); start(to); } else { position = to; paint(); }
  }

  // Opening the library or the options sheet pauses the song (the position is kept: Play resumes it).
  function toggleSheet(which) {
    if (sheet !== which && playing) stop();
    sheet = sheet === which ? null : which;
  }

  function retempo() { if (playing) { const p = songPos(performance.now()); stop(); start(Math.max(0, p)); } }

  const setA = () => (loop = { a: Math.min(position, loop?.b ?? Infinity), b: loop?.b ?? current.durationMs });
  const setB = () => (loop = { a: loop?.a ?? 0, b: Math.max(position, (loop?.a ?? 0) + 500) });

  let lastT = null;
  function paint() {
    lastPaint = performance.now();
    const now = lastPaint;
    const t = playing ? songPos(now) : position;
    const dt = lastT === null ? 0 : now - lastT;
    lastT = now;
    sparks.step(dt, { gravity: 900 * (globalThis.devicePixelRatio || 1) });   // arcade (#2434): sparks fly, the score runs up
    if (Math.round(rolling.step(dt)) !== shownScore) shownScore = Math.round(rolling.value);
    if (!song) return;

    if (playing) {
      if (mode === "play") {
        const missed = judge.advance(t);
        for (const i of missed) { effects.push({ kind: "miss", note: notes[i].note, index: i, at: now }); if (prefs.arcade) arcade("miss", notes[i].note, now); }
        if (missed.length) stats = { score: judge.score, streak: judge.streak, accuracy: judge.accuracy() };
        if (endless) for (const _ of missed) scoreEndless("miss", tf());
        if (hybrid) partFails += missed.length;
        countIn = quietLead ? 0 : t < from ? Math.min(countBeats, Math.ceil((from - t) / beatMs())) : t < from + 450 * tf() ? "GO!" : 0;
        if (quietLead && t >= from) quietLead = false;
      }
      if (hybrid && parts[partIdx]) {                       // hybrid: the part is judged as soon as all its notes are
        if (finishAtEnd) { if (t > current.durationMs + 400) { finish(); status = "Song cleared — every part unlocked!"; return; } }
        else if (retryAt) { if (now >= retryAt) { retryPart(); return; } }
        else {
          const st = partState(notes, judge.result, parts[partIdx]);
          if (st.missed) partFails = Math.max(partFails, 1);
          if (st.done) { partDone(); return; }
          const left = partFails === 0 && st.remaining <= BOMB_FROM ? st.remaining : 0;
          if (left !== bomb) { if (left && prefs.arcade) fuseTick(left); bomb = left; }
        }
      } else if (loop && t >= loop.b) { if (endless) laps++; stop(false); start(loop.a, endless); return; }
      if (!hybrid && t > current.durationMs + 800) {
        if (endless && mode === "play") { laps++; stop(false); start(0, true); } else finish();   // infinite: the next lap
        return;
      }
      if (Math.abs(Math.max(from, t) - position) > 100) position = Math.max(from, t);    // (count-in: stays at the start)
      const ghosting = mode === "play" && aids.ghost;
      const lit = new Set(), ahead = mode === "play" ? 60 * tf() : 0;   // play: keys due now · listen: keys sounding
      if (!ghosting) for (const n of visibleNotes(notes, t, ahead, 0, maxLen)) if (n.start <= t + ahead && n.end >= t) lit.add(n.note);
      if (!sameSet(lit, guide)) guide = lit;
      // The ghost waits as long as a press typically takes to reach the phone, so a perfect press
      // and its ghost light up together (#2429).
      const g = ghosting ? ghostKeys(notes, ghostTime(now), maxLen, GHOST_MIN_MS * tf()) : new Set();
      if (!sameSet(g, ghost)) ghost = g;
      if (aids.fingers || aids.moves) showFingers(t, 3 * beatMs(), aids.moves, Math.max(beatMs(), 500));   // held and due within a beat in full, the next beats faint, and moves
    }

    if (follow) {
      const soon = visibleNotes(notes, t, FOLLOW_AHEAD_MS * tf(), 0, maxLen);
      follow.aim(soon.filter(n => n.start <= t).map(n => n.note), soon.filter(n => n.start > t).map(n => n.note));
      const v = follow.step(dt);
      if (Math.abs(v.x0 - view.x0) > 0.002 || v.span !== view.span) view = { x0: v.x0, span: v.span };
    }
    draw(t, now);
  }

  function draw(t, now) {
    if (!canvas || !stageW || !stageH) return;
    const dpr = globalThis.devicePixelRatio || 1;
    const W = Math.round(stageW * dpr), H = Math.round(stageH * dpr);
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    const ctx = canvas.getContext("2d");
    const v = follow ? { x0: follow.x0, span: follow.span } : view;
    const hitY = H - 3 * dpr, pxPerMs = hitY / AHEAD_MS;
    const xOf = r => { const p = toPct(r, v); return [(p.left / 100) * W, (p.width / 100) * W]; };
    const judged = mode === "play";
    const notation = prefs.notation, showFinger = aids.fingers, showMoves = aids.moves;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (prefs.arcade && now < shakeUntil) {                     // combo milestone: a short screen punch
      const k = (shakeUntil - now) / 200 * 4 * dpr;
      ctx.setTransform(1, 0, 0, 1, (Math.random() - 0.5) * k, (Math.random() - 0.5) * k);
    }
    for (let n = 21; n <= 108; n++) {                          // lanes: black keys darker, a line at each C
      const r = keyRect(n);
      if (r.x + r.w < v.x0 || r.x > v.x0 + v.span) continue;
      const [x, w] = xOf(r);
      if (r.black) { ctx.fillStyle = "rgba(0,0,0,.28)"; ctx.fillRect(x, 0, w, hitY); }
      else if (n % 12 === 0) { ctx.fillStyle = "rgba(255,255,255,.07)"; ctx.fillRect(x, 0, 1 * dpr, hitY); }
    }

    if (!playing) {                                             // finding your place: the keys you tap light their lane (#2431)
      for (const k of liveOn) {
        const r = keyRect(k);
        if (r.x + r.w < v.x0 || r.x > v.x0 + v.span) continue;
        const [x, w] = xOf(r), start = keyFing.has(k);           // green: a key of the starting position
        const g = ctx.createLinearGradient(0, hitY, 0, hitY * 0.35);
        g.addColorStop(0, start ? "rgba(79,209,139,.55)" : "rgba(90,160,255,.45)");
        g.addColorStop(1, "rgba(90,160,255,0)");
        ctx.fillStyle = g;
        ctx.fillRect(x, hitY * 0.35, w, hitY * 0.65);
      }
    }

    const res = judge.result;
    for (const n of visibleNotes(notes, t, AHEAD_MS, PAST_MS, maxLen)) {
      const r = keyRect(n.note);
      let [x, w] = xOf(r);
      if (x + w < 0 || x > W) continue;
      x += 1.5 * dpr; w = Math.max(2 * dpr, w - 3 * dpr);
      const yTop = Math.max(-10, timeToY(n.end, t, hitY, pxPerMs)), yBot = timeToY(n.start, t, hitY, pxPerMs);
      const h = Math.max(6 * dpr, yBot - yTop);
      let color = TRACK_COLORS[Math.max(0, hands.indexOf(n.track)) % TRACK_COLORS.length], alpha = r.black ? 0.85 : 1;
      if (judged) {
        const state = res[n.i];
        if (state === "perfect" || state === "good") color = "#ffd23f";
        else if (state === "early" || state === "late") color = "#ff9f5a";
        else if (state === "miss") color = "#4a4a58";
        if (state === "skip") alpha = 0.25;
      } else if (playing && n.start <= t) {
        color = "#ffd23f";                                      // listen: lit while pisynth plays it
        if (n.end < t) alpha = 0.35;
      }
      let near = 0;                                             // "I play": a note about to land shakes harder and harder
      if (aids.shake && judged && playing && !res[n.i] && n.start > t) {
        const lead = SHAKE_BEATS * beatMs();
        if (n.start - t < lead) {
          near = 1 - (n.start - t) / lead;                      // 0 when it starts shaking … 1 on the line
          x += Math.sin(now * (0.05 + 0.1 * near) + n.i) * near * near * 3.5 * dpr;
        }
      }
      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, yBot - h, w, h, 4 * dpr) : ctx.rect(x, yBot - h, w, h);
      ctx.fill();
      if (near > 0.35) {                                        // and its edge lights up as it gets there
        ctx.strokeStyle = `rgba(255,255,255,${((near - 0.35) / 0.65) * 0.9})`;
        ctx.lineWidth = 2 * dpr;
        ctx.stroke();
      }
      const finger = showFinger && w >= 11 * dpr && h >= 17 * dpr ? fingers[n.i]?.finger : 0;
      let named = false;
      if (w >= 11 * dpr && h >= (finger ? 36 : 13) * dpr) {    // the note's name at its bottom, if it fits (#2418)
        const label = pitchName(n.note, notation);
        const size = Math.min(12 * dpr, w * 0.46, h - 2 * dpr);
        ctx.font = `700 ${size}px system-ui, sans-serif`;
        if (ctx.measureText(label).width <= w - 2 * dpr) {
          ctx.fillStyle = "rgba(13,13,18,.85)";
          ctx.fillText(label, x + w / 2, yBot - 3 * dpr);
          named = true;
        }
      }
      if (showMoves && shifts[n.i] && w >= 9 * dpr && h >= 12 * dpr) {   // a hand move starts here: a green arrow over the note
        const dir = shifts[n.i].dir, cx = x + w / 2, ay = yBot - h - 7 * dpr, s = Math.min(7 * dpr, w * 0.45);
        ctx.fillStyle = "#4fd18b";
        ctx.beginPath(); ctx.moveTo(cx + dir * s, ay); ctx.lineTo(cx - dir * s * 0.6, ay - s * 0.8); ctx.lineTo(cx - dir * s * 0.6, ay + s * 0.8); ctx.fill();
      }
      if (finger) {                                            // the suggested finger, a disc above the name (#2431)
        const rad = Math.min(8 * dpr, w * 0.42), cy = yBot - (named ? 17 * dpr : 2 * dpr) - rad;
        ctx.fillStyle = showMoves && shifts[n.i] ? "#1f8a52" : "rgba(13,13,18,.78)";   // (green: the first finger of a new position)
        ctx.beginPath(); ctx.arc(x + w / 2, cy, rad, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = `800 ${rad * 1.35}px system-ui, sans-serif`;
        ctx.textBaseline = "middle";
        ctx.fillText(String(finger), x + w / 2, cy + rad * 0.06);
        ctx.textBaseline = "bottom";
      }
    }
    ctx.globalAlpha = 1;

    effects = effects.filter(e => now - e.at < 450);            // hit / miss glow on the line
    for (const e of effects) {
      if (e.kind === "wrong") continue;
      const [x, w] = xOf(keyRect(e.note));
      const a = 1 - (now - e.at) / 450;
      ctx.fillStyle = e.kind === "miss" ? `rgba(255,90,90,${a * 0.5})` : `rgba(255,210,63,${a * 0.8})`;
      ctx.fillRect(x - 4 * dpr, hitY - 26 * dpr * a, w + 8 * dpr, 26 * dpr * a);
    }

    if (judged && playing && aids.ghost) {                         // ghost: an outline pulses where a note should be hit
      const pulse = GHOST_PULSE_MS * tf();
      ctx.lineWidth = 2 * dpr;
      for (const p of ghostPulses(notes, ghostTime(now), maxLen, pulse)) {
        const [x, w] = xOf(keyRect(p.note));
        const a = 1 - p.age / pulse, grow = 6 * dpr * (1 - a);
        ctx.strokeStyle = `rgba(255,210,63,${a})`;
        ctx.strokeRect(x + 1.5 * dpr - grow, hitY - 20 * dpr - grow, Math.max(2 * dpr, w - 3 * dpr) + 2 * grow, 20 * dpr + grow);
      }
    }

    ctx.fillStyle = "#ffd23f";                                  // the hit line
    ctx.fillRect(0, hitY, W, 3 * dpr);

    if (prefs.arcade) {                                         // arcade (#2434): shockwave rings + sparks
      ctx.lineWidth = 2 * dpr;
      for (const e of effects) {
        if (e.kind !== "perfect") continue;
        const [x, w] = xOf(keyRect(e.note)), a = 1 - (now - e.at) / 450;
        ctx.strokeStyle = `rgba(255,255,255,${a})`;
        ctx.beginPath(); ctx.arc(x + w / 2, hitY, w / 2 + (1 - a) * 46 * dpr, Math.PI, 2 * Math.PI); ctx.stroke();
      }
      for (const p of sparks.items) {
        ctx.globalAlpha = Math.max(0, 1 - p.age / p.life);
        ctx.fillStyle = p.color;
        ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
      }
      ctx.globalAlpha = 1;
    }

    if (follow) {                                               // arrows: notes coming outside the window
      for (const n of visibleNotes(notes, t, FOLLOW_AHEAD_MS * tf(), 0, maxLen)) {
        const r = keyRect(n.note), left = r.x + r.w <= v.x0, right = r.x >= v.x0 + v.span;
        if (!left && !right) continue;
        const y = Math.max(12 * dpr, timeToY(n.start, t, hitY, pxPerMs));
        const x = left ? 4 * dpr : W - 4 * dpr, s = (left ? 1 : -1) * 10 * dpr;
        ctx.fillStyle = "rgba(255,255,255,.75)";
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + s, y - 7 * dpr); ctx.lineTo(x + s, y + 7 * dpr); ctx.fill();
      }
    }
  }

  $effect(() => { stageW; stageH; view; song; prefs.notation; aids.fingers; aids.moves; liveOn; keyFing; untrack(() => { if (!playing) paint(); }); });   // redraw when idle, resized, renamed or a key is tapped
  onDestroy(() => { stop(); exitPlayMode(); });

  const fmt = ms => { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const pct = ms => `${(Math.min(ms, current.durationMs) / (current.durationMs || 1)) * 100}%`;
  const LABEL = { perfect: "perfect", good: "good", early: "early", late: "late", wrong: "wrong note", miss: "miss" };
</script>

<main>
  <div class="hud">
    <div class="toggle" role="group" aria-label="mode">
      <button class:on={mode === "play"} onclick={() => onMode("play")}>I play</button>
      <button class:on={mode === "listen"} onclick={() => onMode("listen")}>Listen</button>
    </div>
    <span class="lv" title="{lv.into} / {lv.need} XP to the next level">Lv {lv.level}<i style:width="{Math.round((lv.into / lv.need) * 100)}%"></i>
      {#key xpGain?.id}{#if xpGain && !finished}<b class="xp-pop">+{xpGain.xp} XP</b>{/if}{/key}
    </span>
    {#if song && mode === "play"}
      {#if endless}
        <span class="endless" title="infinite mode · best {endlessBook.best(songKey(song))}">∞ {endlessShown}</span>
        {#if laps}<span class="acc">lap {laps + 1}</span>{/if}
      {:else if hybrid && parts.length}
        <span class="score" class:racing={prefs.arcade && shownScore !== stats.score}>{prefs.arcade ? shownScore : stats.score}</span>
        <span class="part" title="{parts[partIdx]?.label} · {cleared} of {parts.length} cleared">
          {#each parts as _, k (k)}<i class:done={k < cleared} class:here={k === partIdx}></i>{/each}
          <b>{partIdx + 1}/{parts.length}</b>
        </span>
      {:else}
        <span class="score" class:racing={prefs.arcade && shownScore !== stats.score}>{prefs.arcade ? shownScore : stats.score}</span>
      {/if}
      {#if stats.streak > 1}<span class="streak">×{stats.streak}</span>{/if}
      <span class="acc">{stats.accuracy}%</span>
    {/if}
    <span class="song">{song ? song.name || "untitled" : ""}</span>
  </div>

  <div class="area">                                  <!-- the notes' area; the sheet floats over it, never resizing it -->
  {#if song}
    <div class="stage" bind:clientWidth={stageW} bind:clientHeight={stageH}>
      <canvas bind:this={canvas}></canvas>
      {#if countIn}{#key countIn}<div class="count" class:go={countIn === "GO!"}>{countIn}</div>{/key}{/if}
      {#if prefs.arcade && playing && hitsShown >= 2}
        {#key hitsShown}<div class="hits"><b>{hitsShown}</b> HITS</div>{/key}
      {/if}
      {#if hybrid && playing && bomb}
        <!-- hybrid: a clean part's last strikes — a number about to go off, shaking and heating up as it gets close -->
        <div class="bomb" style:--k={(BOMB_FROM - bomb) / (BOMB_FROM - 1)} aria-label="{bomb} to unlock the next part">
          {#key bomb}<b>{bomb}</b>{/key}
        </div>
      {/if}
      {#if hybrid && playing && !bomb && partFails > 0}
        {#key partFails}<div class="fails" aria-label="{partFails} mistakes in this part">✗ {partFails}</div>{/key}
      {/if}
      {#if quietLead && playing}<div class="again-cue">↺ {parts[partIdx]?.label}</div>{/if}
      {#key announce?.id}
        {#if announce && prefs.arcade && playing}
          <div class="announce" class:breaker={announce.breaker} style:--tier-color={announce.color}
               style:top="{announce.pos?.y ?? 14}%" style:left="{announce.pos?.x ?? 0}%" style:right="{-(announce.pos?.x ?? 0)}%">
            <Comic splash={announce.splash} text={false} width={announce.breaker ? "min(77vw, 352px)" : "min(67vw, 320px)"} />
            <span class="announce-text">{announce.text}</span>
          </div>
        {/if}
      {/key}
      {#key levelUp?.id}
        {#if levelUp}<div class="levelup-at"><Comic splash={levelUp.splash} kind="levelup" width="min(70vw, 336px)" /></div>{/if}
      {/key}
      {#key oopsAt?.id}
        {#if oopsAt && prefs.arcade && playing}
          <div class="oops-layer"><div class="oops-at" style:left="{oopsAt.x}%"><Comic splash={oopsAt.splash} kind="oops" width="min(32vw, 136px)" /></div></div>
        {/if}
      {/key}
      {#key flash?.id}
        {#if flash && playing && !(prefs.arcade && flash.kind === "wrong")}
          <div class="flash {flash.kind}">{LABEL[flash.kind]}{#if flash.delta !== undefined && flash.kind !== "perfect"} <small>{flash.delta > 0 ? "+" : ""}{Math.round(flash.delta)} ms</small>{/if}</div>
        {/if}
      {/key}
      {#if finished}
        <section class="results">
          {#if best?.newScore && best.previous}<p class="record">NEW RECORD!</p>{/if}
          <h2>{stats.accuracy}%</h2>
          <p><b>{judge.score}</b> points · best streak {judge.bestStreak}</p>
          {#if xpGain}<p class="xp">+{xpGain.xp} XP <small>· <Gauge value={xpGain.diff} />{xpGain.tempo !== 100 ? ` · tempo ×${(xpGain.tempo / 100).toFixed(2)}` : ""}{xpGain.easy < 0.99 ? ` · easy for Lv ${xpGain.before.level} ×${xpGain.easy.toFixed(2)}` : ""}{xpGain.play > 1 ? ` · play ${xpGain.play} today ×${xpGain.repeat.toFixed(2)}` : ""}</small></p>{/if}
          {#if prefs.arcade && combo.maxHits >= 2}<p class="best-combo">max combo {combo.maxHits} hits{combo.bestTierName ? ` · ${combo.bestTierName}` : ""}</p>{/if}
          {#if best?.previous}<p class="muted">best {best.record.score} pts{best.record.tempo !== 100 ? ` at ${best.record.tempo} %` : ""} · {best.record.accuracy}% · {best.record.plays} plays</p>{/if}
          <p class="muted">perfect {judge.counts.perfect} · good {judge.counts.good} · early {judge.counts.early} · late {judge.counts.late} · missed {judge.counts.miss} · wrong {judge.counts.wrong}</p>
          <div class="again">
            <button onclick={() => { finished = false; start(loop?.a ?? 0); }}>Play again</button>
            {#if nextUp}<button class="next" onclick={playNext}>Next ›<small>{displayName(nextUp.path)}</small></button>{/if}
          </div>
        </section>
      {/if}
      {#if error}<p class="error">{error}</p>{:else if status}<p class="status-msg">{status}</p>
      {:else if !playing && !finished && !sheet}<p class="status-msg warmup">Tap your keys to find your place{aids.fingers ? " — the numbers are your fingers" : ""}, then Play</p>{/if}
    </div>
  {:else}
    <div class="live">
      <div class="chord">{detectChord(sounding, prefs.notation) || " "}</div>
      <div class="notes">{sounding.map(n => noteName(n, prefs.notation)).join(" ") || " "}</div>
      <p class="muted hint">Tap the folder to pick a song</p>
    </div>
  {/if}

  {#if sheet}
    <button class="scrim" aria-label="close" onclick={() => (sheet = null)}></button>
  {/if}
  {#if sheet === "library"}
    <section class="sheet">
      <Library current={song?.path} onPick={load} />
      <button class="link" onclick={() => load(sampleSong())}>use the built-in sample</button>
    </section>
  {:else if sheet === "options" && song}
    <section class="sheet">
        {#if mode === "play"}
          <div class="modes" role="radiogroup" aria-label="play mode">
            {#each PLAY_MODES as m (m)}
              <button class:on={prefs.playMode === m} role="radio" aria-checked={prefs.playMode === m} onclick={() => chooseMode(m)}>{MODE_LABEL[m]}</button>
            {/each}
          </div>
          <p class="muted">{#if prefs.playMode === "hybrid"}Part by part: play a part without a wrong key or a missed note to unlock the next. {cleared} of {parts.length} parts cleared.
            {#if cleared}<button class="link" onclick={restartParts}>start over from part 1</button>{/if}
          {:else if prefs.playMode === "infinite"}The song starts over by itself, with a score of its own that goes up with your hits and down with misses and wrong keys.
          {:else}The whole song, once, then your results.{/if}</p>
        {/if}
        <label>Tempo {tempo}% <input type="range" min="50" max="150" step="5" bind:value={tempo} onchange={retempo}></label>
        {#if !hybrid}<div class="loop">
          <span>Loop</span>
          <button class="small" onclick={setA}>A = {fmt(loop?.a ?? position)}</button>
          <button class="small" onclick={setB} disabled={!loop && position === 0}>B = {loop ? fmt(loop.b) : "—"}</button>
          {#if loop}<button class="small ghost" onclick={() => (loop = null)}>clear</button>{/if}
        </div>{/if}
        <p class="muted">Difficulty <Gauge value={songDiff} number /> (for your level: {levelDifficulty(lv.level).toFixed(1)}). Points and XP × the tempo.</p>
        <p class="muted">{hands.length >= 2 ? "2 hands: right hand blue, left hand green. " : ""}{mode === "play" ? "Hit each note as it reaches the yellow line." : "pisynth plays the song; the notes light up as they sound."}</p>
    </section>
  {/if}
  </div>

  <div class="player">
    <button class="play" onclick={() => (playing ? stop() : song ? start() : toggleSheet("library"))} aria-label={playing ? "Stop" : "Play"}>
      {#if playing}
        <svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5" /></svg>
      {:else}
        <svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z" /></svg>
      {/if}
    </button>
    <button class="modebtn {prefs.playMode}" disabled={mode !== "play"} onclick={cycleMode}
            aria-label="play mode: {MODE_LABEL[prefs.playMode]} — tap to change" title="{MODE_LABEL[prefs.playMode]} mode">
      {#if prefs.playMode === "infinite"}∞{:else if prefs.playMode === "hybrid"}<svg viewBox="0 0 24 24"><path d="M7 11V8a5 5 0 0 1 9.9-1h-2.1A3 3 0 0 0 9 8v3h9a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 18 21H6a1.5 1.5 0 0 1-1.5-1.5v-7A1.5 1.5 0 0 1 6 11z" /></svg>{:else}1×{/if}
    </button>
    <button class="replay" disabled={!song} onclick={rewind}
            aria-label={hybrid ? "stop and back to this part's start (tap twice: the first part)" : loop ? "stop and back to A" : "stop and back to the start"}
            title={hybrid ? "Back to this part · tap twice: back to part 1" : ""}>
      <svg viewBox="0 0 24 24"><path d="M12 5V1.5L7 6.5l5 5V7.5a5.5 5.5 0 1 1-5.5 5.5H4a8 8 0 1 0 8-8z" /></svg>
    </button>
    <button class="folder" class:open={sheet === "library"} class:attention={!song} onclick={() => toggleSheet("library")} aria-label="choose a song">
      <svg viewBox="0 0 24 24"><path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h5l2 2h8A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z" /></svg>
    </button>
    <div class="meta">
      {#if song}
        <div class="bar">
          {#if loop}<span class="loopzone" style:left={pct(loop.a)} style:width="calc({pct(loop.b)} - {pct(loop.a)})"></span>{/if}
          <input class="seek" type="range" min="0" max={current.durationMs || 1} step="100"
                 value={Math.min(position, current.durationMs)} onchange={seek} aria-label="position">
        </div>
        <div class="time">{fmt(position)} / {fmt(current.durationMs)}{tempo !== 100 ? ` · ${tempo}%` : ""}{loop ? " · loop" : ""}</div>
      {:else}
        <div class="time">No song loaded</div>
      {/if}
    </div>
    {#if song}
      <button class="more" class:open={sheet === "options"} onclick={() => toggleSheet("options")} aria-label="tempo and loop">
        <svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" /></svg>
      </button>
    {/if}
  </div>
  <Keyboard view={song ? view : null} on={liveOn} demo={guide} {ghost} fingers={song && aids.fingers ? keyFing : null} moves={song && aids.moves && playing ? keyMoves : null} height={song ? "clamp(64px, 19vh, 170px)" : "clamp(90px, 30vh, 240px)"} minHeight="64px" />
</main>

<style>
  main { flex: 1; display: flex; flex-direction: column; min-height: 0; }
  .hud { display: flex; align-items: center; gap: 10px; padding: 4px 12px; font-variant-numeric: tabular-nums; min-height: 38px; }
  .toggle { display: flex; background: #2a2a36; border-radius: 999px; padding: 2px; flex: 0 0 auto; }
  .toggle button { margin: 0; padding: 5px 12px; border-radius: 999px; background: none; color: var(--muted); font-size: .85rem; font-weight: 600; }
  .toggle button.on { background: var(--accent); color: #fff; }
  .score { font-weight: 800; font-size: 1.1rem; color: var(--yellow); }
  .streak { font-weight: 700; color: #4fd18b; }
  /* arcade (#2434) */
  .score { display: inline-block; min-width: 3ch; }
  .score.racing { transform: scale(1.18); text-shadow: 0 0 10px rgba(255,210,63,.7); transition: transform .08s; }
  /* hybrid's countdown, under the HITS counter: the strikes left to unlock the next part — shakes harder,
     beats faster and turns from yellow to red as it gets close, like something about to go off */
  .bomb { position: absolute; top: 40px; right: 10px; width: 56px; text-align: center; pointer-events: none; z-index: 3;
          animation: bomb-shake calc(.3s - var(--k) * .22s) linear infinite; }
  .bomb b { display: inline-block; font: 400 calc(2rem + var(--k) * .9rem)/1 Bangers, Impact, "Arial Black", sans-serif;
            color: hsl(calc(50 - var(--k) * 50), 100%, 60%); -webkit-text-stroke: 2px #000; paint-order: stroke fill;
            text-shadow: 0 0 calc(6px + var(--k) * 16px) hsl(calc(40 - var(--k) * 40), 100%, 55%);
            animation: bomb-pop .3s cubic-bezier(.2,1.8,.4,1); }
  @keyframes bomb-shake {
    0%, 100% { transform: translate(0, 0) rotate(0); }
    25% { transform: translate(calc(var(--k) * 4px + 1px), calc(var(--k) * -3px)) rotate(calc(var(--k) * 16deg + 4deg)) scale(calc(1 + var(--k) * .08)); }
    75% { transform: translate(calc(var(--k) * -4px - 1px), calc(var(--k) * 3px)) rotate(calc(var(--k) * -16deg - 4deg)); }
  }
  @keyframes bomb-pop { from { transform: scale(1.9); } to { transform: scale(1); } }
  /* hybrid, a part already missed: its mistakes (wrong keys, missed notes) in purple where the bomb would be */
  .fails { position: absolute; top: 46px; right: 12px; z-index: 3; pointer-events: none; font: 400 1.5rem/1 Bangers, Impact, "Arial Black", sans-serif;
           color: #b98bff; -webkit-text-stroke: 1.5px #000; paint-order: stroke fill; text-shadow: 0 0 10px rgba(168,107,255,.6);
           animation: bomb-pop .3s cubic-bezier(.2,1.8,.4,1); }
  /* hybrid starting a part again: a discreet marker during the bar before it */
  .again-cue { position: absolute; left: 50%; top: 10px; transform: translateX(-50%); padding: 3px 12px; border-radius: 999px; z-index: 3;
               background: rgba(34,34,46,.85); color: var(--muted); font-size: .8rem; font-weight: 700; pointer-events: none;
               animation: cue-in .4s ease-out; }
  @keyframes cue-in { from { opacity: 0; transform: translate(-50%, -6px); } }
  .hits { position: absolute; top: 8px; right: 10px; font-style: italic; font-weight: 800; font-size: .9rem; color: #fff; pointer-events: none;
          text-shadow: 0 2px 0 #000, 0 0 12px rgba(90,160,255,.8); animation: hitpop .25s ease-out; }
  .hits b { font-size: 1.6rem; color: var(--yellow); }
  @keyframes hitpop { from { transform: scale(1.5); } to { transform: scale(1); } }
  .announce { position: absolute; left: 0; right: 0; top: 14%; text-align: center; pointer-events: none; z-index: 3;
              font-family: Bangers, Impact, "Arial Black", system-ui, sans-serif; font-weight: 400; font-size: clamp(1.5rem, 8.8vw, 2.6rem); letter-spacing: 2px;
              color: #fff; -webkit-text-stroke: 2px #000; paint-order: stroke fill; text-shadow: 0 4px 0 #000, 0 0 22px var(--tier-color);
              animation: slam 1.05s cubic-bezier(.2,1.6,.4,1) forwards; }
  .announce-text { position: relative; }                  /* over its splash bubble */
  /* the OOPS sinks under the yellow hit line: its layer stops just above the line and clips it */
  .oops-layer { position: absolute; inset: 0 0 3px 0; overflow: hidden; pointer-events: none; z-index: 2; }
  .oops-at { position: absolute; bottom: 70px; width: 0; height: 0; }
  .announce.breaker { font-size: clamp(1.2rem, 7vw, 2.1rem); animation: slam 1.05s cubic-bezier(.2,1.6,.4,1) forwards, glitch .12s steps(2) 4; }
  /* slams in, holds a beat, then sinks like a boat — going down faster and faster, listing, fading */
  @keyframes slam { 0% { transform: scale(3) rotate(-8deg); opacity: 0; } 18% { transform: scale(1) rotate(-3deg); opacity: 1; }
                    32% { transform: translateY(0) scale(1.03) rotate(-3deg); opacity: 1; animation-timing-function: cubic-bezier(.35,0,.75,.7); }
                    75% { transform: translateY(14vh) scale(1) rotate(9deg); opacity: 1; animation-timing-function: linear; }
                    100% { transform: translateY(26vh) scale(.94) rotate(16deg); opacity: 0; } }
  @keyframes glitch { 50% { translate: 6px -2px; } }
  .best-combo { color: var(--yellow); font-style: italic; font-weight: 700; }
  .acc { color: var(--muted); font-size: .85rem; }
  /* level (#2436): the number over a thin XP bar; a run's XP floats up from it */
  .lv { position: relative; flex: 0 0 auto; font-weight: 800; font-size: .8rem; color: #c38bff; padding-bottom: 4px; white-space: nowrap; }
  .lv::before, .lv i { content: ""; position: absolute; left: 0; bottom: 0; height: 2px; border-radius: 2px; }
  .lv::before { right: 0; background: rgba(195,139,255,.25); }
  .lv i { background: #c38bff; }
  .xp-pop { position: absolute; left: 0; top: 100%; z-index: 4; color: #e3c8ff; font-size: .85rem; text-shadow: 0 1px 0 #000;
            pointer-events: none; animation: xp-float 2.4s ease-out forwards; }
  @keyframes xp-float { 0% { transform: translateY(6px) scale(.8); opacity: 0; } 12% { transform: none; opacity: 1; }
                        70% { opacity: 1; } 100% { transform: translateY(18px); opacity: 0; } }
  .levelup-at { position: absolute; inset: 0; z-index: 6; pointer-events: none; }   /* over the results card */
  .results .xp { color: #c38bff; font-weight: 800; }
  .results .xp small { font-weight: 500; color: var(--muted); }
  .song { margin-left: auto; color: var(--muted); font-size: .8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .area { flex: 1; position: relative; min-height: 0; display: flex; flex-direction: column; }
  .stage { flex: 1; position: relative; min-height: 0; overflow: hidden; background: linear-gradient(#0d0d12, #17171f); }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
  .live { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 16px; min-height: 0; }
  .chord { font-size: clamp(2.5rem, 14vw, 5rem); font-weight: 800; color: var(--yellow); }
  .notes { font-size: clamp(1rem, 5vw, 1.6rem); color: var(--muted); letter-spacing: 1px; }
  .hint { margin-top: 14px; }
  .count { position: absolute; inset: 0; display: grid; place-items: center; font-size: 5rem; font-weight: 800; color: rgba(255,255,255,.85); pointer-events: none; }
  .count { animation: pop .35s ease-out; }
  .count.go { color: var(--yellow); font-size: 4.5rem; text-shadow: 0 0 24px rgba(255,210,63,.6); }
  @keyframes pop { from { transform: scale(1.6); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  .flash { position: absolute; left: 50%; bottom: 36px; transform: translateX(-50%); font-weight: 800; font-size: 1.1rem; pointer-events: none;
           animation: rise .6s ease-out forwards; text-shadow: 0 2px 6px #000; white-space: nowrap; }
  .flash small { font-weight: 500; font-size: .75rem; opacity: .8; }
  .flash.perfect { color: #ffd23f; } .flash.good { color: #4fd18b; }
  .flash.early, .flash.late { color: #ff9f5a; } .flash.wrong, .flash.miss { color: #ff6b6b; }
  @keyframes rise { from { opacity: 1; transform: translate(-50%, 0); } to { opacity: 0; transform: translate(-50%, -24px); } }
  .results { position: absolute; left: 16px; right: 16px; top: 50%; transform: translateY(-50%); max-height: calc(100% - 12px); overflow-x: hidden; overflow-y: auto; background: rgba(34,34,46,.95);   /* (x: the NEW RECORD pop overflows for a moment) */ border-radius: 14px; padding: 14px 18px; text-align: center; }
  .results h2 { font-size: clamp(1.6rem, 9vh, 2.6rem); color: var(--yellow); }
  .results button { margin-top: 8px; }
  .again { display: flex; flex-wrap: wrap; justify-content: center; gap: 0 10px; }
  .next { background: #2c2c3a; display: inline-flex; flex-direction: column; align-items: center; line-height: 1.15; max-width: 60%; }
  .next small { font-weight: 500; font-size: .7rem; color: var(--muted); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .results p { margin-top: 6px; }
  .results .record { margin: 0 0 2px; font-weight: 900; letter-spacing: .06em; color: var(--yellow); text-shadow: 0 0 12px rgba(255,210,63,.7); animation: record-pop .5s cubic-bezier(.2,1.6,.4,1) both; }
  @keyframes record-pop { from { transform: scale(2.2) rotate(-8deg); opacity: 0; } to { transform: none; opacity: 1; } }
  .error, .status-msg { position: absolute; left: 12px; right: 12px; top: 8px; }
  .error { color: #ff7a7a; }
  .status-msg { color: var(--muted); }
  /* the song / tempo / loop sheet floats over the notes (the lanes keep their size) */
  .scrim { position: absolute; inset: 0; z-index: 5; margin: 0; padding: 0; border-radius: 0; background: rgba(0,0,0,.35); }
  .sheet { position: absolute; left: 8px; right: 8px; bottom: 8px; z-index: 6; max-height: calc(100% - 16px); overflow-y: auto;
           padding: 12px 14px; background: var(--bar); border-radius: 12px; box-shadow: 0 8px 28px rgba(0,0,0,.55); }
  .sheet label { display: block; margin-top: 8px; }
  .sheet input[type="range"] { width: 100%; }
  .sheet p { margin-top: 8px; }
  .link { background: none; color: var(--accent); padding: 4px 0; margin-top: 4px; font-weight: 400; display: block; }
  .loop { display: flex; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .small { margin: 0; padding: 6px 10px; font-size: .85rem; border-radius: 8px; }
  .ghost { background: #3a3a48; }
  .player { display: flex; align-items: center; gap: 10px; padding: 6px 12px; background: var(--bar); }
  .player button { margin: 0; padding: 0; display: grid; place-items: center; flex: 0 0 auto; }
  .play { width: 44px; height: 44px; border-radius: 50%; }
  .play svg { width: 22px; height: 22px; fill: #fff; }
  .replay { width: 40px; height: 40px; border-radius: 50%; background: #2c2c3a; }   /* always there: stop, back to the start (or A) */
  .replay svg { width: 22px; height: 22px; fill: var(--fg); }
  .replay:disabled { opacity: .35; }
  /* ∞ toggle: the song starts over by itself, with its own score */
  /* play mode button: 1× normal · 🔒 hybrid · ∞ infinite (tap to cycle; the ⋯ sheet explains them) */
  .modebtn { width: 40px; height: 40px; border-radius: 50%; background: #2c2c3a; color: var(--fg); font-size: .95rem; font-weight: 800; line-height: 1; }
  .modebtn.infinite { background: #c38bff; color: #121218; font-size: 1.45rem; }
  .modebtn.hybrid { background: #4fd18b; color: #121218; }
  .modebtn svg { width: 20px; height: 20px; fill: currentColor; }
  .modebtn:disabled { opacity: .35; }
  .part { display: inline-flex; align-items: center; gap: 3px; }
  .part i { width: 8px; height: 8px; border-radius: 2px; background: #3a3a48; }
  .part i.done { background: #4fd18b; }
  .part i.here { box-shadow: 0 0 0 2px var(--yellow); }
  .part b { margin-left: 3px; font-size: .75rem; color: var(--muted); }
  .modes { display: flex; gap: 4px; background: #2a2a36; border-radius: 999px; padding: 3px; margin-bottom: 6px; }
  .modes button { flex: 1; margin: 0; padding: 7px 0; border-radius: 999px; background: none; color: var(--muted); font-size: .85rem; }
  .modes button.on { background: var(--accent); color: #fff; }
  .endless { font-weight: 800; font-size: 1.1rem; color: #c38bff; }
  .folder { width: 40px; height: 40px; border-radius: 50%; background: #2c2c3a; }
  .folder svg { width: 22px; height: 22px; fill: var(--fg); }
  .folder.open { background: var(--accent); }
  .folder.attention:not(.open) { box-shadow: 0 0 0 2px var(--yellow); }
  .more { width: 36px; height: 36px; border-radius: 50%; background: none; }
  .more svg { width: 20px; height: 20px; fill: var(--muted); }
  .more.open svg { fill: var(--accent); }
  .meta { flex: 1; min-width: 0; }
  /* sideways (#2419): main's blocks join the app grid (app.css) — score and controls in the side column,
     the notes and the keyboard in the wide one */
  @media (orientation: landscape) {
    main { display: contents; }
    .hud { grid-column: 1; grid-row: 2; flex-wrap: wrap; align-content: flex-start; gap: 8px 10px;
           padding: 6px 8px 6px max(12px, env(safe-area-inset-left, 0)); background: var(--bar); }
    .song { margin-left: 0; flex-basis: 100%; white-space: normal; }
    .area { grid-column: 2; grid-row: 1 / 4; border-left: 1px solid #000; }
    .player { grid-column: 1; grid-row: 3 / 5; flex-wrap: wrap; align-content: flex-end; gap: 10px;
              padding: 8px 8px max(10px, env(safe-area-inset-bottom, 0)) max(12px, env(safe-area-inset-left, 0)); }
    .meta { order: 3; flex-basis: 100%; }
    .more { margin-left: auto; }
    main > :global(.keyboard) { grid-column: 2; grid-row: 4; border-left: 1px solid #000; }
  }
  .bar { position: relative; }
  .loopzone { position: absolute; top: 6px; height: 6px; background: rgba(255,210,63,.35); border-radius: 3px; pointer-events: none; }
  .seek { width: 100%; height: 18px; margin: 0; accent-color: var(--accent); display: block; position: relative; }
  .time { font-size: .75rem; color: var(--muted); font-variant-numeric: tabular-nums; }
</style>
