# Changelog

All notable changes to pisynth, in plain language. Newest first.

## 0.5.0 — unreleased

### Added
- **Metronome "Piano" mode** — the click can now be played by the synth itself, so it
  comes out of the same speakers as the piano (Settings → Metronome → Mode). The click
  sound is a soundfont you can choose; the classic "Separate" mode (its own output card)
  stays available.
- **Tempo presets** — pick a classic tempo (Largo … Presto) on the Metronome screen; the
  BPM stepper still fine-tunes.
- **Home beat pulse** — optional: the Home-screen metronome icon flashes on each beat
  (Settings → Metronome → Home pulse).

### Changed
- **Metronome beat indicator** — a single metronome glyph in the header that blinks in
  time (yellow on the strong beat, blue on the others), instead of a row of dots.
- The Navigation screen is now in English.
- **Audio performance** — fluidsynth now renders polyphony across 2 CPU cores (was 1) and
  the CPU governor is pinned to `performance`, for steadier timing and fewer glitches on
  dense chords / large soundfonts.

### Fixed
- System health no longer warns when the optional MIDI-bridge service is down — only the
  synth (sound) and power/thermal state drive the health indicator.

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
