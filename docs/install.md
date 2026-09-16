# Installing pisynth

Step-by-step, from a blank SD card to playing. Budget ~30–45 min (plus an optional
soundfont download). To hack on the UI **without** a Pi, see [dev.md](dev.md)
(`tools/preview.py`).

> **Heads-up:** pisynth is a build-it-yourself project — you install it from source, so a
> little comfort with the terminal and SSH helps. There's no pre-made image (yet); the steps
> below, plus the official Raspberry Pi guides they link, walk you through it.

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
**sudo password once** if your Pi's sudo requires one. When a step changes boot config (the screen overlay) it **reboots
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

## 8. Web companion on your phone

Tap the **QR icon** next to the metronome on the home screen and scan it with your phone (it must
be on the same Wi-Fi). Add it to your home screen to use it like an app.

**The first time, install pisynth's certificate** (once per phone). The connection is encrypted with
pisynth's own small certificate authority, so no browser trusts it out of the box. The page the QR
opens checks that for you: a phone that already trusts pisynth goes straight to the app, a new one
gets the steps — download `pisynth-ca.crt`, compare its fingerprint with the one on the pisynth
screen, then:
- **Android:** Settings → Security → More security settings → Encryption & credentials → Install a
  certificate → CA certificate.
- **iPhone:** open the page in Safari, download, Settings → Profile Downloaded → Install, then
  Settings → General → About → Certificate Trust Settings → turn on *pisynth local CA*.

**The certificate is optional.** In a hurry, tap **Open pisynth anyway** on that page: the browser
says the connection isn't private (it doesn't know pisynth's certificate), choose *Advanced → Continue*
(Android) or *Show details → visit this website* (iPhone), and the companion works the same. The
warning may come back now and then, and the companion can't be added as an app until the certificate
is installed.

That certificate can only vouch for devices on your local network (names ending in `.local` and
private addresses), never for an internet site. If the Pi gets a new IP address, pisynth renews its
certificate on its own at the next start — the phone keeps trusting it. On a computer,
`./pair.sh --ca` downloads the certificate and says how to import it.

The companion is **one screen**, made for a phone or tablet held sideways: the stage (the score or the
falling notes) and the keyboard take it all. With no song loaded it shows the keys and chord you play, live.

- **The side panel** (☰, top left) holds everything else: **Score | Game**, I play / Listen and normal /
  hybrid / infinite (Game), the musician, the metronome, **Effects & points** (Score), the song's tempo and
  A–B loop, the settings (⚙: **Sound** — soundfont, preset, gain, output, reverb, chorus, MIDI keyboard, the
  pisynth screen follows —, **Metronome**, **Display** — note names in English C D E or French Do Ré Mi —,
  **Musicians**, **Latency** — the key-to-sound delay measured with the phone's microphone —, **About**), and
  the **gallery**.
- **Closed**, it leaves the **mini player** over the stage: ☰, Play / Stop, ↻ (back to the start, or A), the
  song's name, the progress bar, the metronome (Score) and the points (Game, or Score with points on).

Any song or score plays in either mode. In Game mode, **I play**: hit each note as it reaches the yellow
line, your timing is scored; **Listen**: pisynth plays the song, the notes light up as they sound.

**Metronome.** In Score mode (the Game mode has none), while the phone
is connected, it manages pisynth's metronome (in the side panel, "more…" for all of it): start/stop, tempo (−/+, slider, **Tap**, Largo…Presto), beats per
bar, click volume, and lights on the beats. The click is played **by pisynth** (the phone is a remote) or
**by the phone** (headphones, say — pisynth then only counts the beats). Each musician keeps their own
metronome and gets it back on pisynth when they pick up the phone. The pisynth screen keeps only
Start / Stop meanwhile; when the phone leaves, the metronome is pisynth's again. **Click along with
songs** (or the metronome button of the mini player) makes the phone click with the song, at its tempo and time
signature.

**MIDI library.** Songs come from a library kept on the Pi (the gallery's search, or its Folders). It starts with a small **starter** set of classical piano pieces by level
(Public Domain, from the [Mutopia Project](https://www.mutopiaproject.org/), see
`library/midi/SOURCES.md`).

**Scores.** The library also holds sheet music in **MusicXML** (`.musicxml`, `.xml` or compressed
`.mxl`, the open format every notation program exports). A score with the same name as a MIDI file is
that song's score (🎼 in the library); a score on its own is a song you can play too.

**Score | Game.** The switch in the side panel chooses the mode. **Score** (the default) is a music stand,
calm unless you turn **Effects & points** on. The score is drawn on one line, with the note names
(English or French, as under the cog → Display); Play counts a bar in, then the score scrolls under the blue
play line at the **metronome's tempo** (change it in the panel); slide it with a finger to go
back or forward. Each note you play turns green (in time), orange (early or late) or red (missed). A song without a score shows its falling notes. **Game**
is the falling notes game, with effects, points, levels and XP. The companion reopens the song you had last time. The children's songs of the starter set
come with their scores.

**The gallery.** One search over your library and a catalogue of thousands of piano scores kept on pisynth, public
domain or CC0, by composers who died before 1956 or traditional. Type words in any order, without accents
("chop noct", "fur elise", "tchaikovski"); narrow by category (Classical, Folk & traditional, Sacred,
Children, Studies, Dances), level, two hands or melody, composer; order by popularity, ease or title. ★ keeps
a favourite, the clock shows what you played last; both per musician. The catalogue isn't in git: build it
on the PC once, then deploy (it lands in `~/pisynth/scores` on the Pi):

```
python3 tools/score_catalog.py select PDMX.csv        # PDMX.csv from https://zenodo.org/records/14648209
curl -L 'https://zenodo.org/records/14648209/files/mxl.tar.gz?download=1' \
  | tar -xz -C /tmp/pdmx --wildcards --files-from <(sed 's|^|*|' scores/members.txt)
python3 tools/score_catalog.py build /tmp/pdmx
./deploy.sh
```

To add your own songs or scores:
- **from your computer:** put `.mid` / `.musicxml` / `.mxl` files in the repo's `midi/` folder
  (subfolders are kept) and run `./deploy.sh`; delete one there and deploy again to remove it;
- **from the phone:** open a folder in the library and tap **Add here** (or **New folder** first).
  Uploaded files stay on the Pi through deploys, and only they can be deleted from the phone.

Only someone who can see the pisynth screen can pair a phone (the code works once, for 2 minutes),
and **one browser is paired at a time**: the QR icon turns **green** while one is paired, and pairing
another one disconnects it (pisynth warns you first). **Settings → Web companion → Unpair** removes it.

## 9. Optional: read-only mode (safe to unplug)

A synth usually gets switched off at the wall, not shut down. Out of the box pisynth already
keeps its writes to the SD card to a minimum. For full protection, turn on **read-only mode**:
the card is mounted read-only and everything else happens in memory, so pulling the plug can't
corrupt it.

In `pisynth.conf` set `PISYNTH_READONLY=1`, then re-run `./deploy.sh` (or `sudo ./install.sh`
on the Pi). The Pi reboots into read-only mode.

- **Still saved:** what you change on the touchscreen — settings, calibration, Bluetooth pairings.
- **Lost at reboot:** anything else written on the Pi, e.g. soundfonts you copy into
  `~/soundfonts`. Add soundfonts with `./deploy.sh` instead: it switches read-only mode off
  while it works and back on at the end (the Pi reboots twice, automatically).
- **Turn it off:** set `PISYNTH_READONLY=0` and re-deploy. On the Pi directly:
  `sudo pisynth-readonly disable && sudo reboot`.

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
  sudo password once, if your Pi's sudo requires one). Re-run it to update. Add `-UseRsync` if you have rsync on PATH, or
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
