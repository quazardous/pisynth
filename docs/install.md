# Installing pisynth

Step-by-step, from a blank SD card to playing. Budget ~30–45 min (plus an optional
soundfont download). To hack on the UI **without** a Pi, see [dev.md](dev.md)
(`tools/preview.py`).

## 1. What you need

**Hardware**
- Raspberry Pi 3B+ (other 64-bit Pis likely work; tested on the 3B+).
- microSD card (8 GB+).
- 3.5" SPI touchscreen — **ILI9486 + ADS7846** ("goodtft / MPI3501" red board), driven by
  the `piscreen` overlay. Other panels: see [Different screen](#different-screen).
- USB MIDI keyboard (tested: M-Audio Keystation 61 MK3).
- USB audio interface (tested: M-Audio M-Track). The Pi's 3.5 mm jack works but sounds poor.
- Power supply.

**A computer** to flash the card and (optionally) run the one-command deploy. Linux/macOS
work out of the box; Windows users see [Windows](#windows).

## 2. Flash Raspberry Pi OS — and preconfigure it (saves the most pain)

> **Starting point.** pisynth begins from a stock **Raspberry Pi running Raspberry Pi OS,
> reachable over the network, that accepts your SSH key.** Getting there is plain Raspberry
> Pi setup — not pisynth-specific — so this section just points at the **official docs**,
> which stay current with each OS release. Once `ssh <user>@<hostname>.local` works, jump to
> step 3.

This is exactly the Raspberry Pi **headless (remote) setup**. Follow the official guide:

- **Headless setup overview** (no monitor/keyboard, reachable over the network):
  <https://www.raspberrypi.com/documentation/computers/getting-started.html#headless-setup>
- **Install the OS with Raspberry Pi Imager** (Win/macOS/Linux):
  <https://www.raspberrypi.com/documentation/computers/getting-started.html#imager-install>
- **Customise on first boot** — hostname, user, Wi-Fi, SSH (during the Imager write):
  <https://www.raspberrypi.com/documentation/computers/getting-started.html#customisation>
- **Key-based SSH** (generate a key, preconfigure it in the image):
  <https://www.raspberrypi.com/documentation/computers/remote-access.html#configure-ssh-without-a-password>

The whole point is Imager's **OS customisation** screen (⚙ / "Edit settings") — fill it in
**before writing** and it does the most error-prone part of the install in one shot. For
pisynth, set:
- **hostname** (e.g. `pisynth`);
- **username + password** — remember the username, it's the run-as user;
- **Wi-Fi** SSID + password (+ country) and **locale**;
- pick **Raspberry Pi OS (64-bit)** (Trixie / Debian 13);
- under **Services → enable SSH → "Allow public-key authentication"**, paste your SSH
  public key (`~/.ssh/id_*.pub`; create one with `ssh-keygen` if you have none).

Write the card, boot the Pi on the network, and confirm `ssh <user>@<hostname>.local` lands.
That SSH-reachable Pi is the starting point for everything below.

## 3. Wire the screen

Power off, seat the 3.5" SPI panel on the 40-pin header. Power back on. The panel stays
dark until pisynth applies its overlay (step 5) — that's expected.

## 4. Install pisynth — pick one path

### Path A — one command from your computer (Linux / macOS / WSL)
```bash
git clone https://github.com/quazardous/pisynth
cd pisynth
cp pisynth.conf.dist pisynth.conf
# edit pisynth.conf → PISYNTH_HOST=<user>@<hostname>.local   (user/hostname from step 2)
./deploy.sh
```
`deploy.sh` rsyncs the repo to the Pi and runs the installer over SSH, asking the Pi's
**sudo password once**. When a step changes boot config (the screen overlay) it **reboots
the Pi automatically** at the end — the SSH session drops; that's normal.

### Path B — directly on the Pi (any OS, including Windows)
SSH into the Pi (Windows Terminal / PuTTY / a terminal), then:
```bash
sudo apt-get install -y git
git clone https://github.com/quazardous/pisynth ~/pisynth
sudo ~/pisynth/install.sh
```
`install.sh` is the **one-shot end-user installer**: it installs every package in a single
apt batch (from `packages.list`), then hands off to `apply.sh` for the config and a single
reboot. Same result as Path A, no laptop-side scripts. (`sudo bash ~/pisynth/apply.sh`
still works if you've already installed the packages.)

> Path A needs `bash`, `ssh`, `rsync` on your computer **and** key-based SSH (step 2).
> Path B needs only a terminal / SSH client — nothing else runs on your computer.

## 5. What the installer does

`apply.sh` runs ordered, idempotent **migrations** (recorded in `/var/lib/pisynth/applied`),
then a per-deploy **sync**:
- installs fluidsynth + ALSA + the base GM soundfonts;
- enables the `piscreen` screen overlay, gates the desktop to HDMI-only, tidies the console;
- installs the synth + touch-UI services;
- reboots once if boot config changed.

Re-running is safe (only new migrations run). Check progress with
`sudo bash ~/pisynth/apply.sh --status`.

## 6. Soundfonts

The base GM soundfonts (MuseScore General, FluidR3 GM) install automatically. For the
curated grand-piano set (downloaded, ~350 MB), run on the Pi:
```bash
bash ~/pisynth/install-soundfonts.sh
sudo systemctl restart piano.service
```
Or drop your own `.sf2/.sf3` into the repo's `soundfonts/` (Path A) and re-deploy. You can
browse and select soundfonts on the touchscreen even with nothing plugged in.

## 7. Plug in and play

Plug the USB MIDI keyboard and USB audio interface into the Pi. On first boot the
touchscreen runs a **calibration** (tap the 4 targets). Home then shows your soundfonts as
tiles — tap one to select its default sound, tap it again to pick a preset. Press a key.

## Windows

Raspberry Pi Imager (step 2) runs natively on Windows, so the OS prep is identical. For the
install itself, pick one:

- **`install.ps1`** (recommended — native PowerShell wrapper of `deploy.sh`). From a
  `git clone` / unzipped copy of the repo, in PowerShell:
  ```powershell
  Copy-Item pisynth.conf.dist pisynth.conf      # then edit PISYNTH_HOST=user@your-pi
  powershell -ExecutionPolicy Bypass -File .\install.ps1
  ```
  It needs only tools that ship with Windows 10/11 (OpenSSH client, `tar`, `robocopy`): it
  stages the repo, copies it to the Pi over `scp`, then runs `sudo apply.sh` (asks the Pi's
  sudo password once). Re-run it to update. Add `-UseRsync` if you have rsync on PATH, or
  `-PiHost user@host` to override the target.
- **Path B** above — nothing else runs on Windows but an SSH client (Windows Terminal ships
  `ssh`; or use PuTTY): do the `git clone` + `apply.sh` on the Pi. Good for a one-shot
  install with no local repo.
- **WSL** (`wsl --install`, open Ubuntu, `sudo apt install git rsync openssh-client`), then
  follow Path A inside WSL. Best if you want the edit→`./deploy.sh` iteration loop.

The feedback scripts (`shot.sh`, `ctl.sh`, `probe.sh`) are bash + `ssh`; use them from WSL.

## Different screen

The panel is described in [`hardware.conf`](../hardware.conf) (`SCREEN_OVERLAY`,
`SCREEN_OVERLAY_PARAMS`, `SCREEN_SPI`). Edit it for another SPI panel (e.g. `tft35a`,
`mhs35`, `waveshare35a`), then re-apply: `sudo bash ~/pisynth/apply.sh --redo` (or
`./deploy.sh`). Resolution and ADS7846 touch are auto-detected; grid size is Settings →
Tiles per page.

## Troubleshooting

- **`<hostname>.local` won't resolve** → use the Pi's IP: `PISYNTH_HOST=user@192.168.1.50`.
- **deploy keeps asking for a password** → key-based SSH isn't set up (redo step 2's key) —
  or just use Path B.
- **No sound** → the USB audio interface must be plugged in; check `aplay -l` on the Pi and
  **Settings → Audio device**. The synth waits for the card at boot.
- **Screen stays black / shows only a console** → the overlay needs a reboot (the installer
  does it; otherwise `sudo reboot`). Verify with `apply.sh --status`.
- **Backlight won't turn off on screen-sleep** → known hardware limit on the bundled panel
  (backlight hardwired on); see [roadmap.md](roadmap.md).
