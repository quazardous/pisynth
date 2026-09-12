"""Persisted preferences + touch calibration (#303/#308)."""
import json
import os

import yaml

from .persist import request_persist

CAL_PATH = os.path.expanduser(os.environ.get("PISYNTH_CAL", "~/.config/pisynth/touch_cal.json"))
SETTINGS_PATH = os.path.expanduser(os.environ.get("PISYNTH_SETTINGS", "~/.config/pisynth/settings.yaml"))

# Header rewritten into settings.yaml on every save so the live file stays a documented
# template (#303). PyYAML's safe_dump drops comments, hence regenerating this each time.
# A reference copy is committed as settings.yaml.dist; full schema in docs/preferences.md.
SETTINGS_HEADER = (
    "# pisynth local preferences — settings.yaml\n"
    "#\n"
    "# Auto-managed by the touch UI (ui/pisynth/): these are the preferences you\n"
    "# change FROM THE SCREEN (Settings menu). The UI rewrites this file on each change,\n"
    "# so hand-edit it only while pisynth-ui.service is stopped.\n"
    "#\n"
    "# This file holds UI-driven prefs ONLY. System / deployment config lives elsewhere\n"
    "# (kept deliberately separate from these screen preferences):\n"
    "#   ~/.local/synth.conf  — audio card, gain, ALSA buffers, soundfont dir (shell)\n"
    "#   hardware.conf        — SPI screen overlay (shell, in the repo)\n"
    "#\n"
    "# Documented reference + full schema: settings.yaml.dist / docs/preferences.md\n"
)


def _atomic_write(path, text):
    """Write `text` to `path` so a power cut leaves either the old or the new file, never
    an empty/partial one (#681): tmp file, fsync, rename over, fsync the directory."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    request_persist(path)                            # read-only root: write through to the SD


def load_cal():
    try:
        with open(CAL_PATH) as f:
            return json.load(f)["affine"]
    except (OSError, KeyError, ValueError):
        return None


def save_cal(coeffs):
    _atomic_write(CAL_PATH, json.dumps({"affine": coeffs}))


def _legacy_json_path():
    """Pre-#303 JSON settings sat next to the YAML file with a .json suffix."""
    base, _ = os.path.splitext(SETTINGS_PATH)
    return base + ".json"


def load_settings():
    """Load UI preferences from settings.yaml. On first run after the #303 migration
    (no YAML yet) import a legacy settings.json once, persist it as YAML, and return it.
    Returns {} when nothing is present or parseable."""
    try:
        with open(SETTINGS_PATH) as f:
            d = yaml.safe_load(f)
        return d if isinstance(d, dict) else {}
    except FileNotFoundError:
        pass
    except (OSError, yaml.YAMLError):
        return {}
    # one-time import of the old JSON file
    try:
        with open(_legacy_json_path()) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    if isinstance(d, dict) and d:
        save_settings(d)            # rewrite as documented YAML
        return d
    return {}


def save_settings(d):
    """Write UI preferences as documented YAML, atomically and durably (#681)."""
    body = yaml.safe_dump(d, default_flow_style=False, sort_keys=True, allow_unicode=True)
    _atomic_write(SETTINGS_PATH, SETTINGS_HEADER + "\n" + body)
