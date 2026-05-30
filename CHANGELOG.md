# Changelog

All notable changes to pisynth, in plain language. Newest first.

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
