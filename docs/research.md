# pisynth — research & architecture

Goal: port the **nanosynth** synth (NanoPi R4S, headless boot-into-piano, fluidsynth
direct ALSA) onto a **Raspberry Pi 3B+** running **Debian 13 Trixie**, adding a
**3.5" touchscreen (goodtft, ILI9486 + XPT2046/ADS7846 touch) for control**.

Hardware kept: **M-Audio Keystation 61 MK3** (USB MIDI) + **dedicated USB sound card**
(M-Track). Audio output = the USB card (not the Pi's lousy 3.5 mm jack).

---

## Audio decision (validated)

**Direct ALSA, dedicated device.** fluidsynth keeps direct `plughw:` access to the USB
card; we **disable PipeWire** on that card (Trixie enables it by default, unlike the
NanoPi). Minimal latency, faithful to nanosynth. → see the nanosynth note "pure ALSA, no
PulseAudio/JACK".

---

## The control plane already exists

`start-piano.sh` launches fluidsynth in `--server` mode → **TCP server on port 9800**.
`midi-bridge.sh` already drives everything through it (`nc 127.0.0.1 9800` → `select`, `cc`, `noteon`…).

➡️ **Every control frontend = just one more TCP client on 9800.** The touchscreen, the
Keystation D-pad, and a possible web UI all send the same commands to the same place. We
don't touch the audio engine.

```
Keystation 61 MK3 ──USB──┐
                          ├─► fluidsynth (direct ALSA + TCP:9800) ─► USB sound card ─► sound
USB sound card (M-Track) ─┘                  ▲
                                             │ select / cc / gain   (port 9800)
                  ┌──────────────────────────┼───────────────────────────┐
            midi-bridge.sh (D-pad)    3.5" touchscreen GUI (NEW)     [web UI option]
```

---

## Survey of existing projects (for the "mixup")

| Project | Stack | What we take from it |
|---|---|---|
| **Zynthian** (zynthian.org) | Full OS, RT kernel, 50+ engines, screen + encoders + web UI | Architecture inspiration (layers, web UI alongside the physical UI). Too heavy to adopt as-is. |
| **fluidbox** (riban-bw) | C++, wraps fluidsynth, **in-house framebuffer lib `ribanfblib` (NO X)** + buttons | **Reference #1 for the lightweight screen layer**: draws straight to the framebuffer, no X server. |
| **FluidPi** (MarquisdeGeek) | headless fluidsynth + **telnet** + small web server (bashttpd) | Confirms the "control via fluidsynth's TCP port" model. Idea of an optional web UI. |
| **james7780/synth** | C++/**SDL2** fullscreen 800×480, engine + GUI as 2 processes (mqueue) | Fullscreen SDL2 patterns; but a custom engine (not fluidsynth) → less relevant. |
| **serganto/rpi-midi-synth** | Pi Zero 2 W, fluidsynth + SF2, standalone | Confirms fluidsynth+SF2 is viable on a small Pi. |

Mixup conclusion: **nanosynth core (fluidsynth ALSA + TCP 9800)** + **screen layer
fluidbox-style (framebuffer, no X)** + **telnet/TCP control model (FluidPi)**.

---

## Display: as lightweight as possible

Recommendation: **GUI without an X server**, drawing straight to `/dev/fb1`, touch via
evdev (`/dev/input/eventX`). A dedicated mini-X11 (xinit without a WM) is *the simplest*
but not *the lightest* (X server = +~30 MB RAM).

| Approach | X? | RAM | Effort | Note |
|---|---|---|---|---|
| LVGL (C, fbdev+evdev) | no | a few MB | medium | the lightest, region updates (ideal for slow SPI) |
| fluidbox / ribanfblib (C++) | no | a few MB | low | already done for fluidsynth + a small screen |
| Qt/PySide6 `-platform linuxfb` | no | medium | low | no X, but a bigger Qt install |
| pygame/SDL on fb1 | no | light | low | SDL2/fbdev is finicky on Trixie |
| mini-X11 (xinit) + Tkinter | yes | +~30 MB | very low | the simplest, robust touch |

Latency: X vs framebuffer barely matters; what counts is an **event-driven, near-static**
UI (no constant redraw over the slow SPI bus ~16–32 MHz).

**Strategy**: prototype fast with **mini-X11 + Python (Tkinter/pygame)** to validate the
touch ergonomics, then port to **framebuffer (LVGL or ribanfblib)** for the final
lightweight version.

---

## NanoPi → Pi 3B+ / Trixie differences to handle

1. **PipeWire active** (Trixie) → disable it on the USB card so fluidsynth can use direct
   ALSA.
2. **`find_usb_card`** picks the first non-HDMI card → on the Pi it would pick the
   built-in `bcm2835` jack instead of the USB card. Tweak: prefer the `USB-Audio` card
   (marker in `/proc/asound/cards`).
3. **SPI screen under Wayland**: Wayland doesn't drive fb1 (`fbcp` doesn't work under
   Wayland) → we use a dedicated display layer on fb1 (see above).
4. **Screen overlay**: `dtoverlay=piscreen` (ILI9486 + ads7846) + `dtparam=spi=on` in
   `/boot/firmware/config.txt`. Touch calibration needed.
5. **sudo asks for a password** (like on the NanoPi) → interactive installer.

---

## Phases

- **Phase 1 (must-have)**: port the nanosynth core → plug in the Keystation + M-Track,
  adapt `find_usb_card`, disable PipeWire, **get sound** on the Pi.
- **Phase 2 (screen bonus)**: `piscreen` overlay → `/dev/fb1` + touch, calibration; a
  mini-X11/Python GUI prototype talking to 9800; then a lightweight framebuffer port.

---

## Locked decisions (2026-05-20)

- **Base**: lightweight mixup — keep the nanosynth core, not ZynthianOS.
- **Audio**: direct ALSA, dedicated device (PipeWire disabled on the USB card).
- **Display**: GUI **without X**, direct framebuffer on `/dev/fb1` + evdev touch.
  Benefit: the Wayland desktop (HDMI/KMS) and the SPI screen coexist without fighting.
- **Conditional desktop**: `lightdm` only starts if HDMI is plugged in
  (`ExecCondition=/usr/local/bin/pisynth-hdmi-connected`).

### Boot facts observed on the Pi (raspberrypi.local)

- OS Debian 13 trixie, kernel 6.18 aarch64, Pi 3B+, display `vc4-kms-v3d`.
- `systemctl get-default` = `graphical.target`; manager = **lightdm** (active).
- HDMI: `card0-HDMI-A-1 = disconnected` → but the desktop ran anyway (hence the need for
  the HDMI gate).
- Console autologin (`agetty --autologin <user> tty1`) + desktop autologin (lightdm).
- `sudo` asks for a password (no NOPASSWD) → interactive installer.
- Audio available: `bcm2835 Headphones` (jack), `vc4hdmi`. USB sound card + Keystation
  **not yet plugged in** at the time of the survey.

### Files added/modified for the port (in pisynth/)

- `hdmi-connected.sh` → `/usr/local/bin/pisynth-hdmi-connected` (HDMI gate).
- `lightdm-hdmi-only.conf` → drop-in `lightdm.service.d/hdmi-only.conf`.
- `piano.service`: `User=<run-as user>`, RK3399 `CPUAffinity` removed.
- `midi-bridge.service`: `User=<run-as user>`.
- `start-piano.sh`: `find_usb_card` prefers the `USB-Audio` card.
- `setup.sh`: user/paths via `SUDO_USER`/repo, installs the HDMI gate, Trixie.

## Dev workflow (migrations)

Iterating on the remote Pi (where `sudo` asks for a password), DB-migration style:

- `migrations/NNN-*.sh`: ordered, idempotent steps. Each receives `TARGET_USER`,
  `TARGET_HOME`, `REPO_DIR` in its environment.
- `apply.sh` (on the Pi, as sudo): runs the migrations not yet in the ledger
  (`/var/lib/pisynth/applied`). `--status` lists them, `--redo` replays everything.
- `deploy.sh` (on the laptop): **the one command** → `rsync` + `ssh -t sudo apply.sh`.
  Target via `pisynth.conf` (`PISYNTH_HOST`, see `pisynth.conf.dist`).
- `setup.sh`: a shim that calls `apply.sh` (compat).

Loop: edit the code → `./deploy.sh` → it's applied.

Current migrations: 001 packages, 002 runtime (scripts+units+soundfonts), 003 HDMI gate,
004 screen overlay, 005 control GUI.

## Control GUI (chosen tech: Python → framebuffer)

`ui/pisynth-ui.py`: draws RGB565 straight to `/dev/fb0` (Pillow+numpy), reads the ADS7846
touch via evdev, sends `prog`/`gain` to fluidsynth's port 9800. `pisynth-ui.service`
(User=`<run-as user>`, groups video+input). No X. Touch calibration: tap 4 targets → an
affine raw→screen transform (numpy lstsq) saved to `~/.config/pisynth/touch_cal.json`;
`PISYNTH_DEBUG=1` logs raw coords to tune.

## Feedback loop (observe/control the screen remotely)

To iterate on the GUI without touching the panel (and so Claude can see the rendering):

- **Deploy log**: `deploy.sh` tees everything into `deploy.log` (timestamped) → re-read
  the result.
- **Screenshot**: `tools/fbshot.py` reads `/dev/fb0` (RGB565) → PNG.
  - Laptop: `./shot.sh [out.png]` (fetched via SSH). Default `last-shot.png`.
  - Direct: `ssh "$PISYNTH_HOST" 'python3 /usr/local/lib/pisynth/fbshot.py -' > shot.png`
- **Control**: the app listens on a control socket `127.0.0.1:9810`.
  - Laptop: `./ctl.sh state` · `./ctl.sh action next_preset` · `./ctl.sh tap 100 200`
  - Commands: `state`, `render`, `action <next_preset|prev_preset|gain_up|gain_down>`, `tap x y`.
- Observing (`shot.sh`) and controlling (`ctl.sh`) do **not** need sudo (the run-as user
  is in video+input). Only `apply.sh` (installing new code) needs sudo.

### One-shot migrations vs sync on each deploy

- `migrations/NNN-*.sh`: one-time setup (ledger).
- `sync.sh`: replayed on **every** `apply` → re-deploys `ui/*.py`, `tools/*.py`, the
  `/usr/local/bin` scripts, and restarts `pisynth-ui.service`. This is what makes app
  edits take effect on every `./deploy.sh`.

## Sources

- Zynthian — https://zynthian.org/ , https://github.com/eriser/zynthian
- Zynthian on a 3.5" screen — https://github.com/buddhafinger/zyn-rp4-35lcd
- fluidbox — https://github.com/riban-bw/fluidbox
- FluidPi — https://github.com/MarquisdeGeek/FluidPi
- james7780/synth — https://github.com/james7780/synth
- rpi-midi-synth — https://github.com/serganto/rpi-midi-synth
- MIDI sound module + fluidsynth — https://jereme.me/posts/raspberry-pi-midi-sound-module/
