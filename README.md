# pisynth

A Raspberry Pi turned into a standalone **MIDI synthesizer appliance**: plug in a USB
MIDI keyboard and a USB audio interface, power on, and play — with a **touchscreen
control UI** on a small 3.5" SPI display. No desktop, no mouse; it boots straight into
the synth.

Built on **fluidsynth** (SoundFont playback, direct ALSA for low latency) with a
lightweight framebuffer UI (no X / no Wayland) driven by touch — and, soon, by the
keyboard's D-pad.

> Evolved from a headless NanoPi build (`nanosynth`). pisynth adds the touchscreen, a
> menu UI, and a migration-based deploy workflow.

## Features

- 🎹 Boots straight into a playable instrument (any General MIDI SoundFont); hot-swap the
  keyboard or audio interface and it recovers.
- 🖥️ 3.5" touchscreen UI — instrument **tiles** + a **Settings** menu: gain/volume, audio
  output (USB card **or Bluetooth** speaker), a **MIDI device picker + live test keyboard**,
  a **metronome**, system info & **health**, and touch calibration.
- 🪶 Lightweight: framebuffer-direct UI (no X server), fluidsynth in direct ALSA.
- 🔧 One-command **end-user installer** (`install.sh`), or a dev edit-deploy loop with
  idempotent **migrations**; **sideload SoundFonts** over rsync.
- 🖧 Headless-friendly: the HDMI desktop only starts when a monitor is actually attached.

## Hardware

| Part | Tested with |
|------|-------------|
| Board | **Raspberry Pi 3B+**, Raspberry Pi OS *Trixie* (64-bit) |
| Screen | 3.5" SPI, **ILI9486 + ADS7846** ("goodtft/MPI3501" red board) via the `piscreen` overlay |
| MIDI keyboard | **M-Audio Keystation 61 MK3** (USB) |
| Audio out | **M-Audio M-Track** (USB interface) — the Pi 3.5 mm jack works but sounds poor |

Using a different SPI panel? The screen is described in **[`hardware.conf`](hardware.conf)**
(overlay name, SPI speed, rotation); edit it and re-deploy. Resolution and the ADS7846
touch are auto-detected.

## Quick start

> New to this? **[INSTALL.md](docs/install.md)** is the full step-by-step (flashing, SSH keys,
> Windows/WSL, on-device install, troubleshooting). The short version:

First, on the Pi: flash Raspberry Pi OS, enable SSH + key-based login, and wire up the
3.5" screen. Then pick one of two ways to install:

**End user — one command, on the Pi.** Copy this repo onto the Pi (`git clone` there, or
`scp` it over), then:

```bash
sudo ./install.sh        # installs everything in one apt batch, configures, and reboots
```

**Developer — from your computer (edit → deploy loop).**

```bash
git clone https://github.com/quazardous/pisynth
cd pisynth
cp pisynth.conf.dist pisynth.conf      # edit PISYNTH_HOST=user@your-pi
./deploy.sh                            # rsync repo → Pi, run migrations (asks sudo once)
```

Both reboot the Pi themselves when boot config changed (screen overlay, console, splash),
so the first run comes up ready — no manual reboot.

Plug the keyboard + USB audio interface into the Pi. On first boot the screen runs a
**touch calibration** (tap the 4 targets), then shows the instrument tiles. Press a key.

## How it works

```
Keystation 61 MK3 ──USB──┐
                          ├─► fluidsynth (ALSA direct, TCP shell :9800) ─► USB audio ─► sound
USB audio interface ──────┘                  ▲
                                             │ prog / gain commands
                  ┌──────────────────────────┼───────────────────────────┐
            midi-bridge.sh (D-pad)   touch UI (/dev/fb0, control socket :9810)
```

The touchscreen UI (`ui/pisynth-ui.py`) draws straight to the framebuffer and sends
commands to fluidsynth's TCP shell — the same control plane the keyboard D-pad uses. The
desktop (lightdm/Wayland) is gated to start only with HDMI attached, so headless boots go
straight to the synth and the small screen is never fought over.

## SoundFonts

Drop `.sf2` / `.sf3` files into [`soundfonts/`](soundfonts/README.md) and run `./deploy.sh`;
they're synced to the Pi and loaded at startup. System SoundFonts (MuseScore General,
FluidR3 GM) are installed automatically.

## Development

See **[DEV.md](docs/dev.md)** — the deploy workflow, the screenshot/remote-control feedback
loop, the menu-UI SDK, and how to add screens. Design rationale lives in **[RESEARCH.md](docs/research.md)**.
All docs are under **[docs/](docs/)**.

## Status

Work in progress. The touchscreen UI, calibration, and deploy/migration tooling work; the
end-to-end audio path is being validated on hardware. See docs/dev.md / docs/research.md.

## License

[MIT](LICENSE) © 2026 David Berlioz
