#!/usr/bin/env python3
"""preview.py — render the menu UI to PNGs locally (no Pi, no X) for fast UI
iteration. Mocks the framebuffer / touch / fluidsynth and uses a real TTF.

Usage:  python3 tools/preview.py [outdir]      (default: /tmp)
Writes <outdir>/pisynth-{home,presets,presets-p2,settings,audio}.png plus
offline-{home,presets}.png (catalog from .sf files, no synth — #276).
"""
import glob
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "..", "ui", "pisynth-ui.py")
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp"
os.makedirs(OUT, exist_ok=True)
os.environ["PISYNTH_SOUNDS"] = OUT          # metronome click WAVs go here, not ~/.config (#287)

# Stub the device-only deps so the module imports off-device.
ev = types.ModuleType("evdev")
ev.InputDevice = object
ev.list_devices = lambda: []
ev.ecodes = types.SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_TOUCH=330)
sys.modules.setdefault("evdev", ev)
try:
    import numpy  # noqa: F401
except ImportError:
    sys.modules["numpy"] = types.ModuleType("numpy")

spec = importlib.util.spec_from_file_location("pui", UI)
pui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pui)

from PIL import ImageFont
cands = (glob.glob("/usr/share/fonts/**/DejaVuSans-Bold.ttf", recursive=True)
         or glob.glob("/usr/share/fonts/**/*Bold.ttf", recursive=True)
         or glob.glob("/usr/share/fonts/**/*.ttf", recursive=True))
font = cands[0] if cands else None
pui.load_font = lambda sz: ImageFont.truetype(font, sz) if font else ImageFont.load_default()

# ---- mock fluidsynth: the 5 curated soundfonts + per-font preset lists ----
MOCK_FONTS = [
    (1, "01-MuseScore_General.sf3"), (2, "02-FluidR3_GM.sf2"),
    (3, "03-Yamaha-Grand-v2.1.sf2"), (4, "04-Nice-Steinway-Lite-v3.0.sf2"),
    (5, "05-Abbey-Steinway-D-v1.9.sf2"),
]
GM = ["Acoustic Grand", "Bright Piano", "Electric Grand", "Honky-tonk", "Electric Piano",
      "EP Chorused", "Harpsichord", "Clavinet", "Celesta", "Glockenspiel", "Music Box",
      "Vibraphone"]                                  # 12 → 2 pages of tiles


class FakeFB:
    def __init__(self, dev):
        self.w, self.h, self.last = 480, 320, None

    def blit(self, img):
        self.last = img


class FakeTouch:
    def __init__(self):
        self.affine = [1, 0, 0, 0, 1, 0]

    def fileno(self):
        return 0

    def set_affine(self, c):
        self.affine = c

    def map(self, rx, ry):
        a, b, c, d, e, f = self.affine
        return int(a * rx + b * ry + c), int(d * rx + e * ry + f)


class FakeBacklight:                                   # never touch the laptop's real backlight
    path = None

    def set(self, on):
        return False


pui.Framebuffer = FakeFB
pui.Touch = FakeTouch
pui.Backlight = FakeBacklight
pui.SETTINGS_PATH = os.path.join(OUT, "preview-settings.json")   # don't touch the real settings
pui.list_audio_cards = lambda: [("Hub", "M-Track Hub"), ("Headphones", "bcm2835 Headphones")]
# mock the Bluetooth backend so the pairing screen renders off-device (#287)
pui.Bluetooth.open = lambda self: None
pui.Bluetooth.close = lambda self: None
pui.Bluetooth.submit = lambda self, *a: None
pui.Bluetooth.devices = lambda self: [
    ("AA:BB:CC:DD:EE:01", "Sony WH-1000XM4", True, True),
    ("AA:BB:CC:DD:EE:02", "JBL Flip 5", True, False),
    ("AA:BB:CC:DD:EE:03", "Pierre's Buds", False, False),
]

SF_PATHS = [p for _, p in MOCK_FONTS]


def go_online():                                      # synth running: catalog from fluidsynth
    pui.Fluid.connect = lambda self: True
    pui.Fluid.fonts = lambda self: MOCK_FONTS
    pui.Fluid.presets = lambda self, sfid: [(0, i, n) for i, n in enumerate(GM)]
    pui.Fluid.send = lambda self, *cmds: True         # swallow select / gain


def go_offline():                                     # no synth/hardware: catalog from .sf files (#276)
    pui.Fluid.connect = lambda self: False
    pui.Fluid.fonts = lambda self: []
    pui.list_soundfont_files = lambda: SF_PATHS
    pui.read_sf_presets = lambda path: [(0, i, n) for i, n in enumerate(GM)]


# ---- online (synth up) ----
go_online()
app = pui.App()
app.gain = 7.0
app.refresh_fonts()                                   # Home from fluidsynth fonts
app._choose_preset(SF_PATHS[2], 0, 0, "Acoustic Grand")   # current selection (#276)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-home.png"))   # Yamaha framed yellow + preset name

app._open_font(3, SF_PATHS[2])                        # drill into Yamaha Grand → preset tiles
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-presets.png"))
app.cur.page_flip(1)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-presets-p2.png"))

app.stack = [app._home_menu()]
app.sleep_after = 120                                  # show a non-Off value (default is Off, #281)
app.soundcard = "Hub"                                  # show a picked device (#282)
app._open_settings()                                  # categories: Audio/Display/Tools/Info (#289)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-settings.png"))
app.stack.append(app._audio_menu())                   # Settings → Audio (Gain + Audio device)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-audio.png"))
app._open_audio()                                     # → the card picker (#282)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-audio-device.png"))
app.stack = [app._home_menu()]
app.stack.append(app._info_menu())                    # Settings → Info: hardware (#289)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-info.png"))
app.stack = [app._home_menu()]
app.stack.append(app._connectivity_menu())            # Settings → Connectivity (#299)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-connectivity.png"))
app.stack = [app._home_menu()]
app._open_bluetooth()                                 # Connectivity → Bluetooth devices (#287)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-bluetooth.png"))
app.stack = [app._home_menu()]
app.stack.append(app._tools_menu())                   # Settings → Tools (#297)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-tools.png"))
app._confirm_power("Power off", "poweroff")           # confirm screen (render only)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-confirm.png"))
app.stack = [app._home_menu()]
app.stack.append(app._metronome_menu())               # Tools → Metronome (#287)
app.metro.beats = 4; app.metro.running = True; app.metro.beat = 1   # show a running beat (no audio)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-metronome.png"))
app.metro.running = False; app.metro.beat = 0         # leave it stopped (preview only)

# ---- offline (no synth): catalog read straight from the .sf files (#276) ----
go_offline()
off = pui.App()
off.refresh_fonts()                                   # Home from disk, sfid unknown
off._open_font(None, SF_PATHS[0])                     # presets parsed from the file's phdr
off._choose_preset(SF_PATHS[0], 0, 2, "Electric Grand")
off.stack = [off._home_menu()]                        # back Home to show the framed selection
off.render(); off.fb.last.save(os.path.join(OUT, "pisynth-offline-home.png"))
off._open_font(None, SF_PATHS[0])
off.render(); off.fb.last.save(os.path.join(OUT, "pisynth-offline-presets.png"))

print(f"font={font}")
print(f"saved home/presets/presets-p2/settings/audio/audio-device/info + offline-home/offline-presets to {OUT}")
