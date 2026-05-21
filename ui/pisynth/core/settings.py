"""Persisted preferences + touch calibration (#303/#308)."""
import json
import os

import yaml

CAL_PATH = os.path.expanduser(os.environ.get("PISYNTH_CAL", "~/.config/pisynth/touch_cal.json"))
SETTINGS_PATH = os.path.expanduser(os.environ.get("PISYNTH_SETTINGS", "~/.config/pisynth/settings.yaml"))

# Header rewritten into settings.yaml on every save so the live file stays a documented
# template (#303). PyYAML's safe_dump drops comments, hence regenerating this each time.
# A reference copy is committed as settings.yaml.dist; full schema in docs/preferences.md.
SETTINGS_HEADER = (
    "# pisynth local preferences — settings.yaml\n"
    "#\n"
    "# Auto-managed by the touch UI (ui/pisynth-ui.py): these are the preferences you\n"
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


def load_cal():
    try:
        with open(CAL_PATH) as f:
            return json.load(f)["affine"]
    except (OSError, KeyError, ValueError):
        return None


def save_cal(coeffs):
    os.makedirs(os.path.dirname(CAL_PATH), exist_ok=True)
    with open(CAL_PATH, "w") as f:
        json.dump({"affine": coeffs}, f)


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
    """Write UI preferences as documented YAML, atomically (tmp + os.replace)."""
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    body = yaml.safe_dump(d, default_flow_style=False, sort_keys=True, allow_unicode=True)
    tmp = SETTINGS_PATH + ".tmp"
    with open(tmp, "w") as f:
        f.write(SETTINGS_HEADER)
        f.write("\n")
        f.write(body)
    os.replace(tmp, SETTINGS_PATH)
