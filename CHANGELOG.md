# Changelog

All notable changes to pisynth, in plain language. Newest first.

## 0.5.0 — unreleased

### Added
- **Play along (note highway)** — the web companion's Play page drops a song's notes onto the
  keyboard, rock-game style: hit each one as it reaches the yellow line. Your timing is judged
  from the moment you pressed the key (not when Wi-Fi delivered it): perfect, good, early, late,
  missed, with a score, streak and accuracy. Tempo 50–150 %, A–B loop, a count-in played by
  pisynth. Two-hand files show each hand in its own colour; songs wider than the phone slide
  along with the music.
- **Synth settings from the phone** — the web companion's Sound page changes the soundfont and
  preset, gain, output volume and device, reverb, chorus, metronome and MIDI keyboard; the pisynth
  screen follows, and changes made on the box appear on the phone. Reverb and chorus are now real
  settings (remembered, re-applied at start), and the gain is remembered too.
- **Demo mode** — the web companion plays a MIDI file (or a built-in sample) through pisynth's own
  sound, in time; tap the yellow play icon on the pisynth screen to stop it.
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
