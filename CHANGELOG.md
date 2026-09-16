# Changelog

All notable changes to pisynth, in plain language. Newest first.

## Unreleased

### Added
- **A demo of the web companion on GitHub Pages** — https://quazardous.github.io/pisynth/ : the companion
  running in the browser with no Pi. Play with a MIDI keyboard plugged into the computer, the computer keys or
  the keys on screen (a small browser piano sounds them, and Listen), or tick **Let the demo play** to watch the
  game. The starter songs and 300 catalogue scores come along, searchable. Built and published by a GitHub
  Action on every push to main.
- **The metronome on the phone** — in the piano view (a score, or playing freely; not in the game view,
  which switches it off), while the companion is connected it manages pisynth's metronome: a
  Metronome page (the button in the top bar) with start/stop, a big tempo with −/+, a slider, tap tempo
  and the Largo…Presto markings, beats per bar, click volume and lights on the beats. On the phone it
  sounds like a mechanical metronome, tic-toc, brighter on beat 1. Choose who plays
  the click: **pisynth** (through the synth, the phone is a remote) or **this phone** (pisynth then only
  counts the beats, and Start/Stop on its screen starts the phone's click). Each musician keeps their own
  metronome and gets it back on pisynth when they pick up the phone. The pisynth screen shows "Managed by
  the web companion" with just Start/Stop meanwhile; when the phone leaves, everything is back as before.
  **Click along with songs** (the metronome button next to Play) makes the phone click with the song, at
  its tempo and time signature, including the quiet bar before a hybrid part starts again. The phone's click
  is a real mechanical metronome's tick (CC0, BigSoundBank), tic-toc, brighter on beat 1.
- **Find a score** — the library opens on a search through thousands of piano scores kept on pisynth: words in
  any order and without accents, categories (Classical, Folk & traditional, Sacred, Children, Studies, Dances),
  level, two hands or melody, composer, and order by popularity, ease or title; ★ favourites and recently
  played per musician. Only music really out of copyright is kept: public domain or CC0 MuseScore scores
  (through the PDMX dataset) by composers who died before 1956, or traditional tunes. Built on the PC by
  `tools/score_catalog.py` and copied to the Pi by the deploy. Songs often uploaded as "traditional" whose
  composer is still in copyright (Katyusha…) are left out.
- **Classical pieces with their score** — 11 pieces of the starter set (Für Elise, the Bach C major prelude
  and fugue, Chopin preludes, Gymnopédie, Träumerei…) are now scores, from MuseScore editions released as
  CC0 or Public Domain (found through the PDMX dataset): they show in the piano view and play like before, at
  a steady tempo. Handel's Sonatina HWV 585 gets its score beside its MIDI file. Records kept for the old
  MIDI versions of these pieces start over.
- **A simpler screen: the side panel and the mini player** — the stage and the keyboard take the whole screen
  (landscape first). Everything else is in the **panel** that slides in from the left (☰): Score | Game, I play /
  Listen, normal / hybrid / infinite, the musician, the metronome, tempo and loop, the settings, and **one gallery**
  — a single search over your library and the score catalogue. Any song or score plays in any mode. Closed, the
  panel leaves a small **mini player** floating over the stage: ☰, Play / Stop, ↻, the song's name, a progress
  bar that keeps its size, the metronome in Score mode, the points when there are points. Score mode plays
  calmly by default; **Effects & points** in the panel turns on the combos, explosions, points and XP there too.
  Also in the panel for the score: **note names** on or off, and the **score size** (−100 % to +100 %: half to
  double). At the end of the song the blue play line goes away.
- **Two modes: Score | Game** — (now in the side panel). **Score** (the default) is a calm music
  stand: the song you had last time is back, its score on **one line that scrolls under a play line at the
  metronome's tempo** (a bar of clicks to count in); slide it with a finger to go back or forward. As you play,
  each note turns green (in time), orange (early or late) or red (missed). Its top bar: the score library,
  the metronome, the cog — no musician, XP, game modes or arcade. **Game** is the falling notes game: musician,
  level, I play / Listen, normal / hybrid / infinite, the song library, the cog. A song without a score shows
  its falling notes in both. The link status in the top bar is now a dot (green: live).
- **Scores (sheet music)** — the library takes MusicXML scores (`.musicxml`, `.xml`, `.mxl`: the open
  format every notation program exports), from the PC or uploaded from the phone. A score beside a MIDI
  file of the same name is that song's sheet music (🎼); a score on its own is a song you can play,
  listen to and practise like any other. The 🎼 button next to Play shows the score instead of the
  falling notes — note names in English or French, as chosen under the cog → Display, and a cursor
  following the music. The children's songs of the starter set now come with their exact scores.
- **Hand moves shown on the keyboard** — when your hand has to move to a new position, right after the
  key before the move, the keyboard shows both at once: where the hand is (fingers in blue) and where it
  goes (fingers in green), with a green arrow from one to the other. The falling note where the move
  starts wears a green arrow and a green finger disc.
- **All five fingers, always** — the keyboard always shows where each hand's five fingers sit: the
  fingers the coming notes use on their keys, the others on the white keys beside them, very faint.
  The next few beats' fingers are half see-through, so your hand can get ready; they turn solid when
  the note is due.
- **Help options per musician** — finger numbers, hand moves, ghost keys and shaking notes can each be
  switched on or off under the cog → Display ("Help for …"), and each musician keeps their own choice.
- **Play modes: normal, hybrid (the new default), infinite** — pick one in the `⋯` menu, or tap the mode
  button next to Play to cycle. **Hybrid** plays a song part by part: a part must go by without a wrong
  key or a missed note to unlock the next one ("UNLOCKED!"), otherwise it starts again ("TRY AGAIN").
  Parts are a song's phrases or verses when the file marks them, else every 4 bars (8 in a long song);
  the header shows your progress, and each musician's cleared parts are remembered. A part is judged as
  soon as its last note is, so the next one follows on seamlessly. On a clean part, a countdown of the
  strikes left shakes and heats up under the HITS counter like something about to go off; once missed,
  the part's mistakes show there in purple. A missed part keeps its purple count up a moment, then goes
  back with a quick "bzz bzz": a bar to put your hand back, a discreet cue, and its first notes fall
  from the top of the screen.
- **Whole children's songs** — the homer and first steps songs are now complete (all the phrases of
  Au clair de la lune, the whole Ode to Joy theme and Jingle Bells chorus…), each cut into its parts.
- **The musician in the top bar** — a dropdown with who is playing replaces the pisynth title, in that
  musician's colour (each has one; tap its dot under the cog → Musicians to change it).
- **Several musicians** — four on each phone by default (Musician 1 … 4), each with their own level,
  XP, records, infinite-mode bests, cleared parts and help options. Pick who plays from the top bar;
  rename them under the cog → Musicians. What the phone had before becomes Musician 1's.
- **Infinite mode (∞)** — the song starts over by itself, lap after lap (a
  one-beat count-in between laps, the A–B loop if there is one), with a score of its own that climbs
  with the notes you hit and drops with misses and wrong keys. The best it reached is kept per song.
- **Next song** — the results card offers "Next ›": the next song in the folder, or after the last
  one, the first song of the next folder (homer → first steps → …), read from the library on the Pi.
- **Back to the start** — a ↻ button next to Play, always there: it stops the song and goes back to the
  beginning (to A with a loop) with a clean score; press Play when ready. In hybrid mode it goes back to
  the start of the current part, and a double tap back to the first part.
- **No certificate needed to start** — the pairing page now offers "Open pisynth anyway": accept the
  browser's warning once and the companion works without installing pisynth's certificate (installing
  it stays recommended: no warning, installable as an app).
- **Notes shake as they land** — in "I play", a note starts trembling a beat before the yellow line,
  harder and harder, and its edge lights up: you feel the moment coming.

### Changed
- **The companion's offline cache is Workbox's** — the service worker (which keeps the app on the phone
  and updates it with each new version) is now generated by the build with the standard
  vite-plugin-pwa / Workbox, instead of our own template.
- **Smaller, livelier comic splashes** — 20 % smaller, higher up in the lanes, in a new place every time.
- **Fairer, more forgiving timing** — the perfect / good / early-late windows are now a share of the
  beat: a slow song, or a song slowed down with the tempo slider, gives you more time. They are also
  wider overall: a perfect is now at least ±100 ms (was ±50), a good ±200 ms (was ±120).
- **Sideways layout** — with the phone turned sideways, the top bar, score and player controls sit in a
  side column, and the falling notes and keyboard get the whole height.

### Fixed
- The results card no longer shows a stray horizontal scrollbar while "NEW RECORD!" pops in.

## 0.5.0 — 2026-09-13

The web companion release: your phone becomes a play-along coach.

### Added
- **XP and levels** — playing earns XP: the notes you get right, times how hard the song is, times
  the tempo you chose (×0.5 at 50 %, ×1.5 at 150 %). Songs well below your level, and the same song
  again the same day, earn less and less. Your level (Lv) and its XP bar sit in the header; each run
  shows its XP, and a new level pops a "LEVEL UP!" bubble. Kept in the phone's browser.
- **Song difficulty** — each song gets a difficulty from 1 to 10, shown as a 5-bar gauge in the library and
  the `⋯` menu, worked out from how many notes come per second, chords, both hands, black keys
  and how awkward the fingering is.
- **Suggested fingering** — each falling note shows which finger to use (1 = thumb … 5 = little
  finger), and the keyboard shows the finger on the keys coming up. MIDI files carry no fingering, so
  the phone works it out when a song loads, with the usual rules (thumb under, no thumb on black keys
  when avoidable, comfortable spans, chords in order) — the children's songs get the fingering of the
  method books. Switch it off under the cog → Display.
- **Find your place before playing** — with a song loaded and stopped, the keyboard shows the fingers
  of the opening bars, and the keys you tap light up their lane (green on a key the song starts with),
  so you can put your hands in place, then press Play.
- **Arcade effects in "I play"** — hits explode into sparks (a shockwave ring on a perfect), misses
  crumble; streaks of good and perfect hits build combos announced on screen with their own sound
  (TRIPLE, SUPER, HYPER … ULTRA COMBO, perfects count double), a HITS counter, a short screen punch
  on milestones, "COMBO BREAKER" when a big one is lost, the score racing up like an arcade counter,
  and the best combo on the results card. Switch them off under the cog → Display.
- **Comic-book splashes** — each combo slams in over a spiky, halftone comic bubble in its colour
  (a little different in size, place and tilt every time), then both sink like a boat and fade;
  a wrong key pops a purple "OOPS!" bubble with a small sad-trombone, which sinks under the hit line.
  Our own drawings, lettered with the
  Bangers font (SIL Open Font License, bundled so it works without internet).
- **Your best on each song, kept on the phone** — a song played to the end files your best score
  (with its tempo), accuracy, longest combo and number of plays; the results card shows "NEW RECORD!"
  when you beat it, and the library shows your best as ★ next to each song.
- **"Homer" and "First steps" levels, below beginner** — "0 · homer": children's songs with a few notes, right hand only, very slow; "1 · first steps": seven very easy tunes in the MIDI library (Au clair de
  la lune, Frère Jacques, Ode to Joy, Mary had a little lamb, Twinkle twinkle, Jingle Bells and a
  five-finger exercise): the melody in the right hand around C–G, one left-hand note per bar, slow.
  The levels are numbered and list in order, from 0 · homer to 4 · advanced.
- **Note names on the falling notes, in English or French** — each note shows its name (C D E… or
  Do Ré Mi…), and so do the live chord and note readouts. Choose under the cog → Display (a French
  phone starts in French; middle C is Do3 in French notation).
- **No more certificate warning on the phone** — pisynth now has its own small certificate
  authority, limited to your local network. Install it once (the page the pairing QR opens guides
  you and skips the step on a phone that already trusts pisynth), and the companion opens like any
  secure site, installable as an app. The certificate follows the Pi's IP address by itself.
  `./pair.sh --ca` gets it for a computer.
- **Ghost keys in "I play"** — the on-screen keyboard shows the perfect timing as a translucent,
  outlined key next to yours: in time, your blue key gets a yellow outline; early, blue comes
  first; late or missed, the ghost is alone. An outline also pulses in the lane at the exact hit
  moment. The ghost waits for the usual Wi-Fi delay so a perfect press really looks simultaneous.
  On by default; switch it off under the cog → Display.
- **One screen for the web companion** — one player with an "I play / Listen" toggle (the notes
  fall in both; tempo, loop and position are shared), a folder button next to Play to choose a song,
  the live keyboard when no song is loaded, and Sound, Display, Latency and About behind a cog.
  Works in portrait and landscape.
- **MIDI library on the Pi** — the player picks songs from folders kept on pisynth: a starter set
  of 14 classical piano pieces by level (Public Domain, Mutopia Project), your own files from the
  repo's `midi/` folder (synced by `./deploy.sh`, subfolders kept), and files uploaded from the
  phone into any folder. Uploads survive deploys and read-only mode; only they can be deleted
  from the phone. The phone shows each piece's length and whether it has two hands.
- **Play along (note highway)** — "I play" drops a song's notes onto the keyboard, rock-game style:
  hit each one as it reaches the yellow line. Your timing is judged from the moment you pressed the
  key (not when Wi-Fi delivered it): perfect, good, early, late, missed, with a score, streak and
  accuracy. Tempo 50–150 % (the notes fall slower or faster), A–B loop, a "3 · 2 · 1 · GO!"
  video-game count-in played by the phone. Two-hand files show each hand in its own colour; songs
  wider than the phone slide along with the music.
- **Synth settings from the phone** — the companion's cog → Sound changes the soundfont and
  preset, gain, output volume and device, reverb, chorus, metronome and MIDI keyboard; the pisynth
  screen follows, and changes made on the box appear on the phone. Reverb and chorus are now real
  settings (remembered, re-applied at start), and the gain is remembered too.
- **Listen mode** — the web companion plays a MIDI file (or a built-in sample) through pisynth's
  own sound, in time, while its notes fall; tap the yellow play icon on the pisynth screen to stop it.
- **Web companion on your phone** — tap the QR icon next to the metronome and scan it: your phone
  shows the keys you play and the chord name live, and can measure the keyboard-to-sound latency
  with its microphone. Pairing needs the code on the pisynth screen, so only someone at the
  instrument can connect; one phone at a time — the QR icon turns green while one is paired, and
  pairing another one (after a warning) disconnects it.
- **Read-only mode (optional)** — `PISYNTH_READONLY=1` runs the Pi with its SD card read-only,
  so switching it off at the wall can't corrupt it. Screen settings, calibration and
  Bluetooth pairings are still saved; deploying switches the mode off and back on by itself.
- **Metronome click on the piano speakers** — the click is played by the synth itself, so
  it always comes out of the same speakers as the piano, using a fixed light drum soundfont.
  This replaces the old Mode toggle, the separate-output WAV path and the click-sound picker.
- **Tempo presets** — pick a classic tempo (Largo … Presto) on the Metronome screen; the
  BPM stepper still fine-tunes, and the Tempo row shows the matching marking name even for
  in-between tempos (the nearest one).
- **Home beat pulse** — optional: the Home-screen metronome icon flashes on each beat —
  yellow on the strong beat, blue on the others (Settings → Metronome → Home pulse).
- **D-pad metronome toggle** — bind a MIDI key to start/stop the metronome (Settings →
  Navigation → Metronome, learn-by-press).

### Changed
- **A wrong key now costs 25 points** in "I play" (the score never goes below zero), on top of
  breaking the streak.
- **Points follow the tempo** — each note is worth its points × the tempo (50 % → half, 150 % → one
  and a half), so scores and records compare fairly whatever the speed.
- **The web companion's server runs on aiohttp** — the Pi side now uses a standard, well-tested
  web framework (Debian's `python3-aiohttp`) instead of hand-written HTTP and WebSocket code. Nothing
  changes for the phone; notes reach it as fast as before.
- **Gentler on the SD card** — logs are kept in memory, generated sounds live in memory too,
  settings are written safely (a power cut can't leave them empty), and the system no
  longer installs updates on its own in the background.
- **Metronome beat indicator** — a single metronome glyph in the header that blinks in
  time (yellow on the strong beat, blue on the others), instead of a row of dots.
- The Navigation screen is now in English.
- **Audio performance** — fluidsynth now renders polyphony across 2 CPU cores (was 1), runs
  its audio thread at real-time priority, the CPU governor is pinned to `performance`, swap
  is kept off the audio process (`vm.swappiness=10`), and unused NFS/RPC daemons are masked
  — for steadier timing and fewer glitches on dense chords / large soundfonts.

### Fixed
- **Replugging the sound card or keyboard** — unplugging the USB audio interface used to leave
  the synth silent until a restart; it now restarts the sound by itself a few seconds after
  you plug it back. Replugging the keyboard also restores MIDI navigation, keeps the D-pad
  silent, and reconnects a keyboard you picked in Settings → MIDI.
- **Synth control port no longer reachable from the network** — the synth's control port
  (9800) now only accepts connections from the Pi itself, so another computer on your
  network can't change the sound or load files.
- **Keyboard D-pad soundfont switching** — the D-pad now switches soundfonts and presets
  through the touch UI, so it works with the one-soundfont-at-a-time loading, the choice is
  remembered and shown on screen, and it no longer breaks the metronome click or logs
  "No SoundFont with id" errors at boot.
- System health no longer warns when the optional MIDI-bridge service is down — only the
  synth (sound) and power/thermal state drive the health indicator.
- **Navigation beep audible again** — it was silenced by the synth holding the sound card
  exclusively (the beep's `aplay` couldn't open it). The beep is now a short percussion
  note played through the synth itself (reserved channel 9, like the metronome click), so
  it stays consistent whatever instrument is loaded.

## 0.4.0 — 2026-05-30

### Added
- **MIDI navigation** — drive the whole touch UI from your MIDI keyboard's buttons
  (Settings → Navigation): learn a key per action (up / down / left / right / select /
  back), with a configurable feedback beep (sound, kind, volume). The nav keys are kept
  off the synth so they never play a note.
- **Loading indicator** — selecting a soundfont now loads in the background with a
  two-stage on-screen indicator (font load, then sample load) instead of freezing the UI.
- **Live hardware/software info** — the Hardware and Software screens now refresh while
  shown: CPU temperature, clock, power, RAM, disk, uptime and IP update in place.

### Changed
- **Volume range** — gain now spans 0–4.0 in 0.1 steps for finer, wider control.
- **Grid navigation** — menus wrap around at the edges, left/right stay on the row, and
  reaching a page edge flips to the next page.
- **Metronome timing** — the click now streams to a single persistent audio player instead
  of launching one `aplay` per beat, so the tempo stays steady (no more wobble from
  per-beat process startup). Added a **click volume** control on the Metronome screen.

### Fixed
- The navigation beep keeps the sound you chose (it's now a generated tone, independent of
  the loaded soundfont).
- Hardened the background soundfont loader against a boot race that could leave the
  keyboard silent ("No SoundFont with id = …").

## 0.3.0 — 2026-05-21

### Added
- **Bluetooth speaker output** — pick a Bluetooth audio device in Settings → Audio.
- **Metronome** — Settings → Tools → Metronome: set BPM and beats, with a click and beat dots.
- **MIDI keyboard picker** — Settings → MIDI: choose which keyboard plays (or "Auto", all of them).
- **MIDI test keyboard** — a live on-screen piano that lights up as you play, to check your
  keyboard sends notes (works even when the synth isn't running).
- **Audio device picker** — choose the USB sound card, with a "Test sound" button.
- **Home status icons** — Wi-Fi, Bluetooth, keyboard, synth, sound card, metronome, and a
  system-health smiley (green / amber / red).
- **System menu** — hardware & software info, reboot, power off, reset config.
- **Connectivity menu** — separate Wi-Fi / Bluetooth toggles and an airplane mode.
- **One-command installer** — `install.sh` on the Pi (and `install.ps1` for Windows),
  with a shared `packages.list`.

### Changed
- The touch UI was rebuilt as a clean, layered package (core / io / ui / screens) — same
  look, easier to extend.
- Volume steps by 1% and supports press-and-hold; on-screen notices fade by themselves.

### Fixed
- The Bluetooth manager no longer freezes the UI, and audio no longer runs away on the
  Bluetooth / HDMI path.
- The "restarting audio…" notice clears itself, and the audio icon reflects a real sound card.

## 0.2 — earlier
- Touchscreen UI with soundfont/preset tiles, gain control and touch calibration; the
  synth boots straight to a playable instrument; migration-based deploy workflow.
