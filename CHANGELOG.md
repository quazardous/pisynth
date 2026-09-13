# Changelog

All notable changes to pisynth, in plain language. Newest first.

## Unreleased

### Added
- **Hand moves shown in green** — when your hand has to move to a new position, right after the key
  before the move, a green arrow on the keyboard points the way and the new position's fingers light
  up in green; the falling note where the move starts wears a green arrow and a green finger disc.
- **Help options per musician** — finger numbers, hand moves, ghost keys and shaking notes can each be
  switched on or off under the cog → Display ("Help for …"), and each musician keeps their own choice.
- **Play modes: normal, hybrid (the new default), infinite** — pick one in the `⋯` menu, or tap the mode
  button next to Play to cycle. **Hybrid** plays a song part by part: a part must go by without a wrong
  key or a missed note to unlock the next one ("UNLOCKED!"), otherwise it starts again ("TRY AGAIN").
  Parts are a song's phrases or verses when the file marks them, else every 4 bars (8 in a long song);
  the header shows your progress, and each musician's cleared parts are remembered.
- **Whole children's songs** — the homer and first steps songs are now complete (all the phrases of
  Au clair de la lune, the whole Ode to Joy theme and Jingle Bells chorus…), each cut into its parts.
- **The musician in the top bar** — the name of who is playing replaces the pisynth title; tap it to
  choose or rename.
- **Several musicians** — four on each phone by default (Musician 1 … 4), each with their own level,
  XP, records, infinite-mode bests and cleared parts. Rename them and choose who plays under the cog →
  Musicians, or tap the name in the top bar. What the phone had before becomes Musician 1's.
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
- **Fairer, more forgiving timing** — the perfect / good / early-late windows are now a share of the
  beat: a slow song, or a song slowed down with the tempo slider, gives you more time. They are also
  wider overall: a perfect is now at least ±100 ms (was ±50), a good ±200 ms (was ±120).
- **Sideways layout** — with the phone turned sideways, the top bar, score and player controls sit in a
  side column, and the falling notes and keyboard get the whole height.

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
