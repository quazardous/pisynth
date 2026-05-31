#!/usr/bin/env python3
"""preview.py — render the menu UI to PNGs locally (no Pi, no X) for fast UI
iteration. Mocks the framebuffer / touch / fluidsynth and uses a real TTF.

Usage:  python3 tools/preview.py [outdir]      (default: /tmp)
Writes <outdir>/pisynth-{home,presets,presets-p2,settings,audio}.png plus
offline-{home,presets}.png (catalog from .sf files, no synth — #276).
"""
import glob
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
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

sys.path.insert(0, os.path.join(HERE, "..", "ui"))   # the pisynth/ package (#308)
import pisynth.app as pui                             # noqa: E402

from PIL import ImageFont
cands = (glob.glob("/usr/share/fonts/**/DejaVuSans-Bold.ttf", recursive=True)
         or glob.glob("/usr/share/fonts/**/*Bold.ttf", recursive=True)
         or glob.glob("/usr/share/fonts/**/*.ttf", recursive=True))
font = cands[0] if cands else None
_load_font = lambda sz: ImageFont.truetype(font, sz) if font else ImageFont.load_default()
pui.load_font = _load_font                            # legacy/back-compat patch point
import pisynth.ui.renderer as _rend                   # fonts now live on the Renderer (#308)
_rend.load_font = _load_font                          # deterministic font for golden renders

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
    def __init__(self, dev, partial=False):           # partial: #308 io.Framebuffer signature
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
import pisynth.core.settings as _cs                              # settings now live in core/ (#308)
_cs.SETTINGS_PATH = os.path.join(OUT, "preview-settings.yaml")   # don't touch the real settings (#303)
# audio screens + the shared output-device helpers moved into screens/ (#308) → patch there
import pisynth.screens.audio as _sa
import pisynth.screens.devices as _sd
_sa.list_audio_cards = _sd.list_audio_cards = lambda: [("Hub", "M-Track Hub"), ("Headphones", "bcm2835 Headphones")]
_sd.list_bt_sinks = lambda: [("AA:BB:CC:DD:EE:01", "Sony WH-1000XM4")]   # connected A2DP sink (#301)
_sa.alsa_volume = lambda card: 70                # output volume stepper (#314)
_sa.set_alsa_volume = lambda card, pct: True
_sa.bt_volume = lambda mac: 52                   # BT sink volume via wpctl (#314)
_sa.set_bt_volume = lambda mac, pct: True
# MIDI navigation (#373): deterministic ports off-device, and never spawn aseqdump
import pisynth.screens.nav as _snav
_snav.list_midi_ports = lambda: [("Keystation 61 MK3:0", "Keystation 61 MK3:0"),
                                 ("Keystation 61 MK3:1", "Keystation 61 MK3:1")]
_snav.midi_route_to_fluid = lambda port, connect: None    # no aconnect off-device
pui.MidiMonitor.open = lambda self, port: None
pui.MidiMonitor.close = lambda self: None
pui.App._nav_set_bridge = lambda self, active: None        # no systemctl off-device
# Info page (#316): deterministic Pi-like values off-device
pui.board_model = lambda: "Raspberry Pi 3 Model B Plus"
pui.local_ip = lambda: "192.168.1.42"
pui.cpu_temp = lambda: "47°C"
pui.cpu_clock = lambda: "1400 MHz"               # CPU clock line (#325)
pui.list_midi_inputs = lambda: [("Keystation 61 MK3", "Keystation 61 MK3")]   # MIDI picker (#326)
pui.health = lambda: ("good", "OK")              # health smiley + Hardware row (#325)
pui.power_status = lambda: "OK"
pui.mem_info = lambda: "742 / 906 MB free"
pui.disk_info = lambda: "7.3 / 29 GB (27%)"
pui.os_pretty = lambda: "Debian GNU/Linux 13 (trixie)"
pui.uptime_str = lambda: "1h 12m"
# mock the Bluetooth backend so the pairing screen renders off-device (#287)
pui.Bluetooth.open = lambda self: None
pui.Bluetooth.close = lambda self: None
pui.Bluetooth.submit = lambda self, *a: None
pui.Bluetooth.devices = lambda self: [
    ("AA:BB:CC:DD:EE:01", "Sony WH-1000XM4", True, True),
    ("AA:BB:CC:DD:EE:02", "JBL Flip 5", True, False),
    ("AA:BB:CC:DD:EE:03", "Pierre's Buds", False, False),
]
pui.App._poll_status = lambda self, force=False: None   # Home indicators: flags set directly here (#306)

SF_PATHS = [p for _, p in MOCK_FONTS]


def _preview_apply(self):                             # synchronous select off-device (no thread / no real
    sfid = self._sfid_for_path(self.cur_font_path)    # connection): the async load (#375) needs a live synth
    if sfid is not None:                              # so stub it to the old behaviour for deterministic renders
        self.fs.select(sfid, *self.cur_bp)
    return True
pui.App._apply_preset = _preview_apply


def go_online():                                      # synth running: one font loaded, catalog from disk (#334)
    pui.Fluid.connect = lambda self: True
    pui.Fluid.fonts = lambda self, overall=2.0: MOCK_FONTS
    pui.Fluid.presets = lambda self, sfid: [(0, i, n) for i, n in enumerate(GM)]
    pui.Fluid.send = lambda self, *cmds: True         # swallow select / gain / load / unload
    pui.list_soundfont_files = lambda: SF_PATHS       # catalog is the disk set, not fluidsynth's (#334)
    pui.read_sf_presets = lambda path: [(0, i, n) for i, n in enumerate(GM)]


def go_offline():                                     # no synth/hardware: catalog from .sf files (#276)
    pui.Fluid.connect = lambda self: False
    pui.Fluid.fonts = lambda self, overall=2.0: []
    pui.list_soundfont_files = lambda: SF_PATHS
    pui.read_sf_presets = lambda path: [(0, i, n) for i, n in enumerate(GM)]


# ---- online (synth up) ----
go_online()
app = pui.App()
app.gain = 3.0                                        # within the 0–4 stepper range (#372)
app.refresh_fonts()                                   # Home from fluidsynth fonts
app._choose_preset(SF_PATHS[2], 0, 0, "Acoustic Grand")   # current selection (#276)
app._st_wifi = app._st_bt = app._st_midi = app._st_audio = True   # Home top-bar indicators all lit (#306/#327)
app._st_bt_conn = True                                    # BT device connected → bluetooth_connected glyph (#306)
app.metro.running = True                                   # metronome indicator lit (#306)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-home.png"))   # Yamaha framed green (loaded) + preset name
app._loading = True; app._load_phase = 1                 # phase 1: loading the font → amber frame (#375)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-home-loading.png"))
app._load_phase = 2                                      # phase 2: loading the preset samples → blue frame (#375)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-home-loading-samples.png"))
app._loading = False; app._load_phase = 0
app._st_wifi = app._st_bt = app._st_bt_conn = app._st_midi = app._st_audio = False; app._online = False; app.metro.running = False  # nothing on (#306)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-home-idle.png"))
app._health = "warn"                                       # health smiley: amber grimace (#325)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-home-health-warn.png"))
app._health = "good"
app._st_wifi = app._st_bt = app._st_midi = app._online = app._st_audio = True   # restore for later screens
app.metro.running = False                                  # leave metro stopped for later screens

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
app.toast("Audio restarted ✓", secs=999)             # toast SDK overlay (#320)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-toast.png"))
app._toast_msg = ""                                   # clear for later screens
app._open_audio()                                     # → the card picker (#282) + BT sinks (#301)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-audio-device.png"))
app.stack.pop(); app.soundcard = ""; app.bt_sink = "AA:BB:CC:DD:EE:01"   # BT sink chosen (#301)
app._open_audio()
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-audio-device-bt.png"))
app._prompt_audio_restart()                           # mini yes/no restart dialog (#311)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-restart-dialog.png"))
app.stack.pop()                                       # close the dialog
app.soundcard = "Hub"; app.bt_sink = ""               # restore for later screens
app.stack = [app._home_menu()]
app.stack.append(app._info_hardware())                # System → Hardware (temp/power/RAM/disk, #316)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-info-hardware.png"))
app.stack.pop(); app.stack.append(app._info_software())   # System → Software (#316)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-info-software.png"))
app.stack = [app._home_menu()]
app.nav_cfg["enabled"] = True; app.nav_cfg["sound"] = True   # show toggles 'on' (#373)
app._open_nav()                                       # Settings → Navigation (MIDI nav config)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-navigation.png"))
app.nav_cfg["enabled"] = False; app.nav_cfg["sound"] = False
app.stack = [app._home_menu()]
app.stack.append(app._connectivity_menu())            # Settings → Connectivity (#299)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-connectivity.png"))
app.stack = [app._home_menu()]
app._open_bluetooth()                                 # Connectivity → Bluetooth devices (#287)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-bluetooth.png"))
app._bt_open_device("AA:BB:CC:DD:EE:02", "JBL Flip 5", True, False)   # per-device menu (#301)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-bluetooth-device.png"))
app.stack = [app._home_menu()]
app.stack.append(app._system_menu())                  # Settings → System: Hardware/Software/MIDI/Reboot/… (#300/#326)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-system.png"))
app._open_midi()                                       # Settings → MIDI keyboard picker (#326/#330)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-midi.png"))
app.midimon.active = {60, 64, 67}; app.midimon.lo = 60; app.midimon.hi = 67   # C-E-G held (#331)
app.midimon.last, app.midimon.count = 67, 3
app.stack.append(pui.MenuScreen("Test keyboard", [], keyboard=True))   # MIDI test mini-keyboard
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-midi-keyboard.png"))
app.stack.pop(); app.stack.pop()
app._confirm("Reset config", app._reset)              # confirm screen (render only — reset not run)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-confirm.png"))
app.stack = [app._home_menu()]
app.stack.append(app._metronome_menu())               # Tools → Metronome (#287)
app.metro.beats = 4; app.metro.running = True; app.metro.beat = 1; app.metro.flash = True  # strong-beat dot lit (#648)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-metronome.png"))
app.metro.running = False; app.metro.beat = 0; app.metro.flash = False   # leave it stopped (preview only)
app.metro.device = "card:Headphones"                   # show a chosen output device (#668)
app._open_metro_output()                               # Metronome → Output (device picker, #668)
app.render(); app.fb.last.save(os.path.join(OUT, "pisynth-metronome-output.png"))

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
