# pisynth — developer guide

How to work on pisynth. Design rationale and the decision log are in **[research.md](research.md)**.

## Repo layout

```
deploy.sh              # laptop: the one command — rsync + remote apply (logs to deploy.log)
apply.sh               # Pi (sudo): run pending migrations, then sync.sh
sync.sh                # Pi (sudo): re-deploy app/scripts/units/soundfonts every apply
migrations/NNN-*.sh    # one-time, ordered, idempotent setup steps (ledger: /var/lib/pisynth/applied)
shot.sh                # laptop: pull a PNG of the Pi screen (via tools/fbshot.py)
ctl.sh                 # laptop: send a command to the UI control socket (:9810)
pisynth.conf(.dist)    # deployment config (PISYNTH_HOST); pisynth.conf is gitignored
ui/pisynth/            # the framebuffer touch UI package (run via `python3 -m pisynth`)
                       #   app.py = controller; io/ · core/ · ui/ being extracted
tools/fbshot.py        # dump /dev/fb0 (RGB565) to PNG
tools/preview.py       # render the UI to PNGs locally (mock fb/touch) — no Pi needed
start-piano.sh         # fluidsynth launcher (ALSA direct, TCP shell :9800)
midi-bridge.sh         # Keystation D-pad → touch UI (:9810) preset/soundfont switching
*.service              # systemd units: piano, midi-bridge, pisynth-ui (+ lightdm gate drop-in)
soundfonts/            # drop .sf2/.sf3 here to sideload
```

## Configuration

`PISYNTH_HOST` (`user@host` of your Pi) is read from `pisynth.conf` — copy it from
`pisynth.conf.dist` and edit. The env var overrides the file:

```bash
cp pisynth.conf.dist pisynth.conf      # then set PISYNTH_HOST
PISYNTH_HOST=pi@otherpi ./deploy.sh    # one-off override
```

`pisynth.conf` is gitignored so your real host never lands in version control.

`PISYNTH_USER` (optional, same file) sets the user the synth runs as on the Pi —
systemd `User=`, owner of `~/soundfonts`, in `video`+`input`. If unset, `apply.sh`
falls back to whoever ran `sudo` (`SUDO_USER`). The repo's `*.service` files ship a
neutral `User=pi` placeholder that `sync.sh`/migration 002 rewrite to this user on
every deploy — so the username is never hardcoded. Set `PISYNTH_USER` when the SSH
user and the run-as user differ. (`pisynth.conf` is rsync'd with the repo, so
`apply.sh` reads it on the Pi.)

### Local config on the Pi

Runtime config lives in the run-as user's home (not in the repo):

| Path | What | Set by |
|---|---|---|
| `~/.config/pisynth/settings.yaml` | UI prefs: `soundcard`, `sleep_after`, `page_tiles`, `preset`, `metro`, `bluetooth`. Documented; template = `settings.yaml.dist`, schema = [preferences.md](preferences.md) | the touch UI |
| `~/.config/pisynth/touch_cal.json` | touch calibration (affine transform) | first-run / Settings → Display → Calibrate |
| `/run/pisynth/sounds/` | generated sounds (metronome click SMF, test tune) — tmpfs, regenerated on demand | the UI (`RuntimeDirectory=`, #681) |
| `~/.local/synth.conf` | synth config: `GAIN`, `SOUNDCARD`, latency, soundfont dir | migration 002 (from `synth.conf.example`); editable |
| `~/soundfonts/` | loaded soundfonts (`.sf2/.sf3`, often symlinks) | migration 002 / `install-soundfonts.sh` / sideload |

**Settings → System → Reset config** deletes `settings.yaml` (back to defaults) and reverts
the live session; it keeps calibration, `synth.conf`, and soundfonts. None of this is in git
(it's per-device); `pisynth.conf` (the laptop's deploy target) is the only repo-adjacent
config and is gitignored.

## Deploy workflow

Edit on the laptop, then:

```bash
./deploy.sh        # rsync repo → $PISYNTH_HOST:~/pisynth, then `sudo apply.sh` (sudo may prompt, depending on your Pi)
```

`apply.sh` is a migration runner (think DB migrations):

- Runs each `migrations/NNN-*.sh` **not yet recorded** in `/var/lib/pisynth/applied`, in order,
  recording each on success. Re-running applies only new ones.
- Then runs **host-local** one-shots from `local-migrations/NNN-*.sh` the same way (ledger key
  `local/<name>`). That folder is gitignored but rsync'd by `deploy.sh`, like `pisynth.conf`:
  use it for per-device tweaks that must not ship to every install.
- Then **always** runs `sync.sh`.
- `sudo bash ~/pisynth/apply.sh --status` lists applied/pending; `--redo` re-runs all.

**Migrations vs sync — when to put code where:**

- `migrations/NNN-*.sh` → **one-time** setup (apt installs, enabling services, editing
  `config.txt`/`cmdline.txt`, the lightdm HDMI gate). Append a new numbered file; never
  edit an already-applied one to change behaviour (the ledger won't re-run it — add a new
  migration instead).
  - **Needs a reboot?** A migration that changes boot config (`cmdline.txt`, `config.txt`,
    overlays) must append a reason line to `$PISYNTH_REBOOT_FLAG` when it actually changes
    something. `apply.sh` reboots the Pi at the end of the deploy if any migration did — so
    the reboot ships with `./deploy.sh`, no manual step. Skip it with `PISYNTH_NO_REBOOT=1`.
- `sync.sh` → **every deploy**: installs `ui/*.py`, `tools/*.py`, the runtime shell scripts,
  the systemd unit files (with `User=` rewritten to the target user), links sideloaded
  soundfonts, and restarts `pisynth-ui` (and audio services if already running). Edits to
  app code or unit files take effect here automatically.

**Read-only root (`PISYNTH_READONLY=1`, #681):** Raspberry Pi OS's `overlayroot` (RAM overlay
over a read-only SD root), driven by `readonly.sh` → `/usr/local/sbin/pisynth-readonly
status|enable|disable|persist`.
- **Deploy with the overlay active:** `apply.sh` disables it, reboots and exits **75**.
  `deploy.sh` waits for SSH, then rsyncs + applies again on a writable root. `apply.sh`
  re-enables the overlay last (reboot flag). Result: 2 automatic reboots.
- **Write-through:** code that saves user state calls `core.persist.request_persist(path)`.
  It is debounced 5 s and runs `sudo -n pisynth-readonly persist …` (grant: migration 021),
  which remounts `/media/root-ro` rw, copies (or deletes / mirrors) the path, then remounts ro.
  Only whitelisted paths are accepted: `settings.yaml`, `touch_cal.json`, `web_sessions.json`, `/var/lib/bluetooth`.
  A new kind of persisted state must be added to that whitelist.
- **Keep it off on a dev Pi:** every deploy then costs two reboots.

## Feedback loop (no physical access)

```bash
./shot.sh [out.png]                 # pull a screenshot of the SPI panel (default last-shot.png)
./ctl.sh state                      # query UI state
./ctl.sh menu down | up | select | back
./ctl.sh menu adjust 1              # nudge the selected value (e.g. gain)
./ctl.sh action gain_up | gain_down | next_preset | prev_preset
./ctl.sh tap 120 200                # simulate a touch at screen coords
python3 tools/preview.py [outdir]   # render Home + Settings to PNGs locally (no Pi)
```

`shot.sh` and `ctl.sh` need no sudo (the user is in `video`+`input`); only `apply.sh` does.
`tools/preview.py` mocks the framebuffer/touch so you can iterate on the UI offline.

## Web companion dev stack (laptop, Docker)

The phone app (`web/app`, Svelte) and its Pi-side server (`web/`, `python3 -m web`) can be
developed without deploying: `make help` lists everything.

```bash
make dev        # docker compose: pisynth-web (simulated MIDI) + Vite dev server with hot reload
make pair       # one-time pairing URL + QR code in the terminal → scan it with the phone
make dev-pi     # same stack, MIDI bridged from the Pi's real keyboard over SSH (pisynth.conf)
make logs       # both containers · make stats → relay latency p50/p99, clients, frames
make build      # Svelte → web/static (commit it: the Pi serves the built files, no Node there)
make tunnel     # forward the companion running ON the Pi to https://localhost:28443
make down
```

- **Ports on the laptop:** `https://<LAN IP>:15173` (Vite, hot reload; proxies `/pair`, `/api`,
  `/ws` to the server), `https://<LAN IP>:18443` (the built app, served exactly as on the Pi),
  `127.0.0.1:9811` (admin API, never on the LAN). Override with `APP_PORT` / `WEB_PORT` / `ADMIN_PORT`.
- **Certificate:** self-signed, generated once in `dev/certs/` (gitignored). The phone shows a
  warning the first time; HTTPS is required for the microphone (latency page) and the service worker.
- **MIDI sources** (`PISYNTH_WEB_MIDI_SOURCE`): `sim` plays a scale, chords with the sustain pedal
  and an arpeggio in a loop (`SIM_SPEED=2 make dev` to speed it up); `pi` runs
  `ssh $PISYNTH_HOST aseqdump` on the Pi's first hardware keyboard; `aseqdump` (default, on the Pi).
- The server restarts on any Python edit under `web/`; Svelte edits hot-reload in the browser.
- If the phone can't connect, check the laptop firewall allows TCP 15173/18443.
- **Desktop browser / Claude in Chrome** (no cert warning): `make pair-local` → open the
  `http://localhost:15174/#k=…` URL it prints (Chrome treats `http://localhost` as a secure
  context, so the session cookie, mic and service worker still work). `make pi-local` serves the
  local app on that port against the **real server on the Pi**; mint the token with
  `ssh $PISYNTH_HOST curl -s -XPOST http://127.0.0.1:9811/admin/token`.

### Control socket JSON API (web companion, #2417)

Besides the text commands (`ctl.sh`), the UI's control socket (127.0.0.1:9810) accepts JSON lines:
`{"op":"get"}` → `{ok, state, catalog}`; `{"op":"set","key":…,"value":…}` → `{ok, error?, state}`
(keys: `preset` {font,bank,prog}, `font`, `gain`, `volume`, `output` {kind:card|bt|auto,id},
`fx.reverb` / `fx.chorus` {on,…}, `metronome` {running,bpm,beats,vol}, `midi_keyboard`);
`{"op":"watch"}` keeps the connection and streams `{state}` on every change. pisynth-web relays
`get`/`set` from the paired phone and the watch stream back (`web/uilink.py`). Every `set` runs the
touch screen's own code path — the UI remains the only owner of the synth state.

## Tests & lint (laptop, no Pi)

```bash
uvx ruff check ui tools tests                  # lint (config in pyproject.toml)
uvx --with numpy,pillow,pyyaml pytest          # unit tests in tests/
```

Nothing to install system-wide (`uv` fetches the tools). The tests cover the logic that runs
without hardware: calibration fit, settings/calibration files, soundfont preset parsing,
metronome click SMF, D-pad grid navigation, soundfont cycling, and the fluidsynth client
(against a fake TCP shell). `tests/test_layers.py` enforces the package layering:
`core` ↛ `io` ↛ `ui` ↛ `screens` ↛ `app` — a lower layer never imports an upper one.
`evdev` is stubbed in `tests/conftest.py` when absent.

## Architecture

- **Audio** — `start-piano.sh` runs `fluidsynth --server` with `--audio-driver=alsa` on the
  USB interface (`plughw:<card>`), `midi.autoconnect=1`, and the TCP shell on **:9800**.
  Managed by `piano.service` (RT priority, `Restart=always`). PipeWire is masked off the
  USB card so fluidsynth owns it.
- **Control plane** — everything that changes a sound sends a line to fluidsynth's TCP shell
  (`prog <ch> <n>`, `gain <x>`, …). The touch UI owns it; `midi-bridge.sh` goes through the
  UI's control socket (:9810) so the single-font loader and the screen stay in sync.
- **UI** — `ui/pisynth/` package (`python3 -m pisynth`), pure framebuffer (no X):
  - `Framebuffer` writes RGB565 to `/dev/fb0` (Pillow + numpy).
  - `Touch` reads the ADS7846 via evdev and maps raw→screen with a saved **affine** transform.
  - `Fluid` is the :9800 client.
  - A **menu SDK**: `MenuScreen(title, items[, tiles])` + `Item(...)`. Navigation goes through
    `nav_move / nav_select / nav_adjust / nav_back / nav_page`, so touch, the control socket, and
    the MIDI keyboard's D-pad (Settings → Navigation) all drive the same code. Tile grids paginate at `PAGE_TILES` (9)
    with a `p/N` indicator top-right (tap to flip); tabular sub-screens have a standardized back button.
  - **Two-level soundfont UI**: Home tiles come from fluidsynth `fonts` (one per
    loaded soundfont); tapping one drills into its presets from `inst <id>` (bank-0 first); tapping
    a preset issues `select <ch> <sfid> <bank> <prog>` on the keyboard channels (0–14, 15 reserved
    for the bridge SFX). Offline, Home shows a "Waiting for synth…" tile and refreshes once :9800 is up.
  - A **control socket** on **:9810** mirrors the nav API for remote testing (`ctl.sh`):
    `menu up|down|select|back|page|adjust <n>`, `action gain_up|gain_down|next_preset|prev_preset|next_font|prev_font|first_font|beep`,
    `state`, `render`, `refresh`, `tap x y`, `calibrate`, `settings`.

### Adding a menu screen

```python
def _effects_menu(self):
    return MenuScreen("Effects", [
        Item("Reverb", on_adjust=lambda d: self._set_reverb(... + d),
             value=lambda: f"{self.reverb:.1f}"),
        Item("Back-to-X", on_select=self.nav_back),
    ])
# push it from an Item: Item("Effects", on_select=lambda: self.stack.append(self._effects_menu()), submenu=True)
```

`Item` fields: `on_select` (enter), `on_adjust(±1)` (left/right, gives − / + stepper on
touch), `value` (callable → right-aligned text), `marker` (callable → ● current),
`bar` (callable → 0..1 inline VU), `submenu` (chevron). Sub-screens get the back button
and chrome for free.

### Touch calibration

First launch (no `~/.config/pisynth/touch_cal.json`) or **Settings → Calibrate** runs it:
tap 4 targets → least-squares affine (numpy) → saved → a live-dot check until **Done**.
Re-run anytime with `./ctl.sh calibrate`.

## Gotchas

- **No X anywhere** — the UI draws to `/dev/fb0` directly so it coexists with the (HDMI-only)
  desktop. On this board the SPI panel *is* `/dev/fb0`.
- **Plymouth / console** — on a headless boot the desktop is gated off, so plymouth is
  dismissed by `pisynth-ui.service` and the text console is kept off the panel
  (`fbcon=map:1`), or both would bleed onto the UI.
- **`sudo` may ask a password** on the Pi (your sudoers choice) → then `apply.sh`/`deploy.sh` prompt once.
- **Trixie ships PipeWire** — different from the original headless build; it's masked off the
  USB card so direct-ALSA fluidsynth works.

## Conventions

- Keep the UI **event-driven and mostly static** — the SPI bus is slow (~16 MHz); avoid
  continuous full-frame redraws.
- Don't commit `pisynth.conf`, `deploy.log`, screenshots, or large `.sf2/.sf3` (see `.gitignore`).
