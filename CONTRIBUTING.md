# Contributing

Thanks for your interest in **pisynth** — a Raspberry Pi turned into a standalone MIDI
synthesizer appliance (USB MIDI keyboard + USB audio → fluidsynth, with a touchscreen
control UI on a 3.5" SPI screen).

## Reporting bugs

Open an issue on the GitHub tracker with:

- What you tried to do.
- What you expected to happen.
- What actually happened (paste error messages / unexpected output; `deploy.log` and the
  `pisynth-ui` / `piano` service logs are good sources).
- Your environment: Raspberry Pi model, Raspberry Pi OS version, and the USB audio / MIDI
  hardware in use.

A short reproducible description is worth pages of prose.

## Getting help

For usage questions (vs. bug reports), open an issue and tag it `question`. The design
notes and rationale live in `docs/research.md`; tuning guidance in `docs/optimization.md`.

## Development setup

pisynth is developed on a laptop and run on the Pi — you don't edit on the Pi.

1. Copy `pisynth.conf.dist` to `pisynth.conf` and set `PISYNTH_HOST` to your Pi
   (`user@host`). Set up key-based SSH to it.
2. Edit on the laptop, then deploy:
   ```
   ./deploy.sh        # rsync the repo to the Pi, then run the migrations + sync
   ```
   `deploy.sh` reboots the Pi itself when a migration changed boot config — no manual
   reboot needed.

### Working without the Pi

- `python3 tools/preview.py` — render the touch UI to PNGs **locally** (mock framebuffer /
  touch / synth), no Pi required. This is the fastest way to iterate on UI changes and the
  de-facto smoke test: run it before sending a UI change.

### Inspecting a running Pi (read-only)

- `./probe.sh [name|'<command>']` — read-only diagnostics over SSH (audio / MIDI / services /
  UI). By contract it never deploys or modifies the appliance.
- `./shot.sh [out.png]` — pull a PNG of the live SPI screen.
- `./ctl.sh <cmd>` — drive the UI over its control socket for remote testing.

## Sending a pull request

1. Fork and branch off `main` (one feature per branch).
2. Keep diffs focused — small PRs review fast.
3. Before opening the PR:
   - `python3 -m compileall ui/pisynth` — must pass.
   - `python3 tools/preview.py` — must run clean; eyeball the rendered screens for UI changes.
4. Open the PR. Describe the **what** and the **why**; mechanical diff details belong in the
   commit messages, not the PR body.

There is no automated test suite yet — pure-logic helpers under `ui/pisynth/core/` are the
natural place to start adding `pytest` coverage; contributions welcome.

## Code style

- **English everywhere** — identifiers, comments, docstrings, UI strings, commit messages.
- The UI is framebuffer-direct (no X/Wayland): draw via Pillow/numpy to `/dev/fb0`, read
  touch via evdev. Keep hardware access behind the `ui/pisynth/io/` adapters.
- Update `CHANGELOG.md` for any notable change.

## Commit messages

Keep the subject line ≤ 72 chars, imperative mood (`fix steady metronome timing`), followed
by a blank line and a body that explains the **why**.

## Code of conduct

Be kind and assume good faith.
