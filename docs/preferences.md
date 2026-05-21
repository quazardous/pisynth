# Local preferences — `settings.yaml`

> Ticket #303. pisynth's **UI-driven** preferences live in a single documented YAML file.
> A reference template is committed as [`settings.yaml.dist`](../settings.yaml.dist).

## Where

```
~/.config/pisynth/settings.yaml
```

Overridable with the `PISYNTH_SETTINGS` env var (the UI service and `start-piano.sh`
both honour it). The file is **created and rewritten automatically by the touch UI** —
you don't copy the template into place. To edit by hand, stop the UI first
(`sudo systemctl stop pisynth-ui`), edit, then start it again.

On every save the UI regenerates a documented comment header (PyYAML's `safe_dump`
strips comments) and writes atomically (`tmp` + `os.replace`).

## What belongs here — and what doesn't

This file holds **only preferences you change from the screen** (the Settings menu).
David's rule (#303): keep UI-driven prefs distinct from system/deploy config. The
**non-UI / "root" config stays in separate files** and is *not* mirrored here:

| Layer | File | Format | Examples |
|---|---|---|---|
| UI preferences | `~/.config/pisynth/settings.yaml` | YAML | soundcard, screen sleep, preset, metronome, bluetooth |
| System / deploy | `~/.local/synth.conf` | shell vars | `GAIN`, `SOUNDCARD`, ALSA buffers, `SOUNDFONT_DIR` |
| Hardware | `hardware.conf` (repo) | shell vars | SPI screen overlay |
| Touch calibration | `~/.config/pisynth/touch_cal.json` | JSON | affine transform (separate concern) |

## Schema

| Key | Type | Default | Set from | Notes |
|---|---|---|---|---|
| `soundcard` | string | `""` | Settings → Audio → Audio device | ALSA card id (`plughw:NAME`); `""` = auto-detect USB card. Also read by `start-piano.sh`; `synth.conf`'s `SOUNDCARD` overrides. |
| `sleep_after` | int | `0` | Settings → Display → Screen sleep | seconds before screen sleep; `0` = never. |
| `page_tiles` | int | `6` | Settings → Display → Tiles per page | soundfont tiles per Home page (4/6/9/12). |
| `preset` | map | unset | Home: tap soundfont → preset | `{font, bank, prog, name}`; `font` = soundfont basename; re-applied when the synth comes online. |
| `metro` | map | `{bpm:100, beats:4, card:""}` | Settings → Tools → Metronome | `bpm` 40-240, `beats` 1-8, `card` = ALSA card for the click (`""` = system default; pick a card *different* from `soundcard`). |
| `bluetooth` | map | `{audio_sink:"", ble_midi:"", known:{}}` | Settings → Connectivity → Bluetooth devices | `audio_sink`/`ble_midi` = MACs of preferred devices (pisynth's *choices*; populated by the BT manager, #303 slice B). `known` = MAC→friendly-name cache so known devices keep a name with scan off / before BlueZ resolves it (#301, auto-managed). Pairing/trust itself is owned by BlueZ. |

## Migration from `settings.json`

Before #303 these prefs were in `~/.config/pisynth/settings.json`. On the first UI run
after upgrading, `load_settings()` imports the legacy JSON once and rewrites it as YAML
(zero data loss). `start-piano.sh` also falls back to reading the old JSON for `soundcard`
until the UI has run once. `Settings → System → Reset config` removes both files.

PyYAML (`python3-yaml`) is installed by migration `014-pyyaml.sh`.

## Reset

`Settings → System → Reset config` deletes `settings.yaml` (and any leftover legacy
`settings.json`), reverting to defaults. Touch calibration, `synth.conf`, and soundfonts
are kept.
