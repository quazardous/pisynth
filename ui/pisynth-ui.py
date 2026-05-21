#!/usr/bin/env python3
"""pisynth-ui — lightweight touch/menu control for the 3.5" SPI screen.

No X / no Wayland: draws RGB565 straight to the framebuffer (/dev/fb0) and
reads taps from the ADS7846 touchscreen via evdev. Talks to fluidsynth's TCP
shell (:9800), same control plane as midi-bridge.sh.

Two-level Metro tile UI (ticket #276):
  - Home  = one tile per loaded SOUNDFONT (queried via fluidsynth `fonts`).
  - Tap a soundfont → its PRESETS as tiles (queried via `inst <id>`); tap a
    preset → `select <ch> <id> <bank> <prog>` on every keyboard channel.
  - Top-right shows PAGINATION (page p/N) when a grid spans several pages —
    tap it to flip pages. (Replaces the old offline indicator.)
  - Settings tile = gain stepper, audio-device picker, screen sleep,
    touch calibration, version.

Every action goes through a navigation API (move / select / adjust / back /
page) so it can be driven by touch now and by the Keystation D-pad later (and
by the control socket :9810 for remote testing):
    menu up|down|select|back|page   |  menu adjust <-1|+1>
    action gain_up|gain_down|next_preset|prev_preset
    tap <x> <y>  |  state  |  render  |  calibrate  |  settings  |  sleep | wake

Screen sleep (ticket #277): after an inactivity delay (Settings → Screen sleep)
the panel blanks and the backlight powers off (/sys/class/backlight, migration
010); the next touch only wakes it.

First launch (or Settings → Calibrate) runs touch calibration: tap 4 targets →
affine raw->screen transform (numpy lstsq) saved to ~/.config/pisynth/touch_cal.json,
then a live-dot check until "Done".

Deps: python3-pil python3-numpy python3-evdev  (migration 005).
"""
import glob
import json
import os
import re
import selectors
import socket
import struct
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from evdev import InputDevice, ecodes, list_devices

FB_DEV   = os.environ.get("PISYNTH_FB", "/dev/fb0")
FS_HOST  = os.environ.get("FS_HOST", "127.0.0.1")
FS_PORT  = int(os.environ.get("FS_PORT", "9800"))
CTL_PORT = int(os.environ.get("PISYNTH_CTL_PORT", "9810"))
CAL_PATH = os.path.expanduser(os.environ.get("PISYNTH_CAL", "~/.config/pisynth/touch_cal.json"))
DEBUG    = os.environ.get("PISYNTH_DEBUG") == "1"
# Framebuffer paint strategy (#284). "full" = rewrite the whole RGB565 frame every
# render (simple, what we shipped). "partial" = write only the changed row band,
# and skip the write entirely when nothing changed — far less traffic on the slow
# SPI panel (~16-32 MHz). Set PISYNTH_RENDER=partial in pisynth-ui.service to switch.
RENDER_MODE = os.environ.get("PISYNTH_RENDER", "full")
VERSION  = "0.2"

# Keyboard channels we broadcast preset changes to. Channel 15 is left alone
# (midi-bridge.sh reserves it for the D-pad feedback SFX).
KBD_CHANNELS = range(15)

SETTINGS_PATH = os.path.expanduser(os.environ.get("PISYNTH_SETTINGS", "~/.config/pisynth/settings.json"))
# Where soundfonts live on disk — same default as start-piano.sh's SOUNDFONT_DIR.
# Used to build the font/preset catalog OFFLINE (no synth/hardware), ticket #276.
SOUNDFONT_DIR = os.path.expanduser(os.environ.get("PISYNTH_SOUNDFONT_DIR", "~/soundfonts"))
# Screen-sleep delays offered in Settings (ticket #277). 0 = never sleep.
SLEEP_OPTIONS = [(0, "Off"), (30, "30s"), (60, "1m"), (120, "2m"), (300, "5m"), (600, "10m")]
# Off by default — auto-blanking surprised the user (#281). Opt in via Settings.
SLEEP_DEFAULT = 0

BG     = (18, 18, 24)
FG     = (235, 235, 240)
MUTED  = (120, 124, 140)
ACCENT = (90, 160, 255)
BARBG  = (34, 36, 48)
SELBG  = (44, 48, 66)
BTN    = (52, 56, 74)
OK     = (90, 200, 120)
ERR    = (220, 90, 90)
TILE_PALETTE = [
    (41, 128, 185), (142, 68, 173), (22, 160, 133), (211, 84, 0),
    (39, 174, 96), (192, 57, 43), (52, 73, 94), (199, 77, 135),
]
TILE_SETTINGS = (90, 98, 120)
TILE_MUTED    = (48, 50, 62)

PAGE_TILES = 6          # tiles per page (3×2 default); changed in Settings → Tiles per page (#276)
PAGE_TILES_OPTIONS = [4, 6, 9, 12]   # choices in Settings → Tiles per page (#276)
LIST_ROWS = 6           # rows per page on list screens — recomputed from screen height by App (#276)
SEL_BORDER = (245, 205, 50)     # yellow frame on the current font/preset tile (#276)
SEL_SUB    = (248, 232, 150)    # selected preset name shown under the font tile (#276)


def load_font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def font_label(path):
    """Pretty display name from a soundfont path: 01-MuseScore_General.sf3 → 'MuseScore General'."""
    base = os.path.basename(path)
    base = re.sub(r"\.(sf2|sf3)$", "", base, flags=re.I)
    base = re.sub(r"^\d+\s*[-_]\s*", "", base)        # strip "01-" load-order prefix
    return (base.replace("_", " ").replace("-", " ").strip()) or base


def solve_affine(raws, screens):
    """Least-squares affine raw (rx,ry) -> screen (sx,sy)."""
    m = np.array([[rx, ry, 1.0] for rx, ry in raws])
    a = np.linalg.lstsq(m, np.array([s[0] for s in screens], float), rcond=None)[0]
    b = np.linalg.lstsq(m, np.array([s[1] for s in screens], float), rcond=None)[0]
    return [float(v) for v in (*a, *b)]


class Framebuffer:
    def __init__(self, dev):
        self.dev = dev
        node = os.path.basename(os.path.realpath(dev))
        with open(f"/sys/class/graphics/{node}/virtual_size") as f:
            self.w, self.h = (int(v) for v in f.read().strip().split(","))
        self.partial = RENDER_MODE == "partial"     # #284: dirty-row updates
        self._prev = None                           # last frame, for diffing

    @staticmethod
    def _encode(img):
        """PIL image -> (h, w) little-endian RGB565 array."""
        arr = np.asarray(img.convert("RGB"), dtype=np.uint16)
        rgb565 = ((arr[..., 0] >> 3) << 11) | ((arr[..., 1] >> 2) << 5) | (arr[..., 2] >> 3)
        return rgb565.astype("<u2")

    @staticmethod
    def _row_band(prev, frame):
        """Smallest [r0, r1) row range covering every row that differs between two
        frames. None when identical; full range when prev is missing/mismatched."""
        if prev is None or prev.shape != frame.shape:
            return (0, frame.shape[0])
        diff = np.any(frame != prev, axis=1)
        if not diff.any():
            return None
        rows = np.nonzero(diff)[0]
        return (int(rows[0]), int(rows[-1]) + 1)

    def blit(self, img):
        frame = self._encode(img)
        if not self.partial:
            with open(self.dev, "wb") as f:
                f.write(frame.tobytes())
            return
        band = self._row_band(self._prev, frame)
        self._prev = frame
        if band is None:
            return                                  # nothing changed: no SPI traffic
        r0, r1 = band
        if r0 == 0 and r1 == self.h:
            with open(self.dev, "wb") as f:
                f.write(frame.tobytes())
        else:                                       # seek to the changed band only
            with open(self.dev, "r+b") as f:
                f.seek(r0 * self.w * 2)
                f.write(frame[r0:r1].tobytes())


class Backlight:
    """SPI panel backlight via /sys/class/backlight/*/bl_power (0=on, 4=off).
    No-op if absent or not writable — migration 010 grants `video` write access."""

    def __init__(self):
        found = glob.glob("/sys/class/backlight/*/bl_power")
        self.path = found[0] if found else None

    def set(self, on):
        if not self.path:
            return False
        try:
            with open(self.path, "w") as f:
                f.write("0" if on else "4")        # FB_BLANK_UNBLANK / POWERDOWN
            return True
        except OSError:
            return False


class Fluid:
    """Client for fluidsynth's TCP shell (:9800). Fire-and-forget for control
    commands (gain/select); query() for listings (fonts/inst)."""

    def __init__(self, host, port):
        self.host, self.port, self.sock = host, port, None

    @property
    def online(self):
        return self.sock is not None

    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=1)
            self.sock.settimeout(0.3)
            self._drain()                              # swallow any banner/prompt
        except OSError:
            self.sock = None
        return self.online

    def _drain(self):
        try:
            while self.sock.recv(4096):
                pass
        except OSError:
            pass

    def send(self, *cmds):
        if not self.online and not self.connect():
            return False
        try:
            self.sock.sendall(("\n".join(cmds) + "\n").encode())
            self._drain()                              # keep the socket reply buffer clean
            return True
        except OSError:
            self.sock = None
            return False

    def query(self, cmd, idle=0.3, overall=2.0):
        """Send a command and collect the reply lines (read until idle)."""
        if not self.online and not self.connect():
            return []
        try:
            self.sock.settimeout(idle)
            self.sock.sendall((cmd + "\n").encode())
        except OSError:
            self.sock = None
            return []
        chunks, deadline = [], time.time() + overall
        while time.time() < deadline:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                break
            except OSError:
                self.sock = None
                break
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks).decode(errors="ignore").splitlines()

    def fonts(self):
        """[(sfid, path), ...] of loaded soundfonts, in load order."""
        out = []
        for ln in self.query("fonts"):
            m = re.match(r"\s*(\d+)\s+(.*\.(?:sf2|sf3))\s*$", ln, re.I)
            if m:
                out.append((int(m.group(1)), m.group(2)))
        return out

    def presets(self, sfid):
        """[(bank, prog, name), ...] for a soundfont (fluidsynth `inst`)."""
        out = []
        for ln in self.query(f"inst {sfid}"):
            m = re.match(r"\s*(\d+)-(\d+)\s+(.+?)\s*$", ln)
            if m:
                out.append((int(m.group(1)), int(m.group(2)), m.group(3)))
        return out

    def select(self, sfid, bank, prog):
        cmds = []
        for ch in KBD_CHANNELS:
            cmds += [f"cc {ch} 0 0", f"cc {ch} 32 0", f"select {ch} {sfid} {bank} {prog}"]
        self.send(*cmds)

    def set_gain(self, gain):
        self.send(f"gain {gain:.2f}")


class Touch:
    def __init__(self):
        self.dev = None
        for path in list_devices():
            d = InputDevice(path)
            if "ADS7846" in d.name or "Touchscreen" in d.name:
                self.dev = d
                break
        if self.dev is None:
            raise RuntimeError("no ADS7846 touchscreen found in /dev/input")
        os.set_blocking(self.dev.fd, False)
        self.affine = None
        self._rx = self._ry = None
        self._touching = False

    def fileno(self):
        return self.dev.fd

    def set_affine(self, coeffs):
        self.affine = coeffs

    def map(self, rx, ry):
        a, b, c, d, e, f = self.affine
        return int(a * rx + b * ry + c), int(d * rx + e * ry + f)

    def read_taps(self):
        """Non-blocking drain → mapped (x, y) taps, reported on release.
        ADS7846 sends BTN_TOUCH press before the coords, so latch on press."""
        taps = []
        try:
            events = list(self.dev.read())
        except BlockingIOError:
            return taps
        for ev in events:
            if ev.type == ecodes.EV_ABS:
                if ev.code == ecodes.ABS_X:
                    self._rx = ev.value
                elif ev.code == ecodes.ABS_Y:
                    self._ry = ev.value
            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                if ev.value == 1:
                    self._touching = True
                elif ev.value == 0 and self._touching:
                    self._touching = False
                    if self.affine and self._rx is not None and self._ry is not None:
                        taps.append(self.map(self._rx, self._ry))
        return taps

    def wait_raw_tap(self):
        """Block for one press+release; return raw (rx, ry)."""
        rx = ry = None
        touching = False
        for ev in self.dev.read_loop():
            if ev.type == ecodes.EV_ABS:
                if ev.code == ecodes.ABS_X:
                    rx = ev.value
                elif ev.code == ecodes.ABS_Y:
                    ry = ev.value
            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                if ev.value == 1:
                    touching = True
                elif ev.value == 0 and touching and rx is not None and ry is not None:
                    return (rx, ry)


class Item:
    """One menu cell/row. on_select = enter; on_adjust(±1) = left/right change."""

    def __init__(self, label, on_select=None, on_adjust=None,
                 value=None, marker=None, bar=None, submenu=False, color=None,
                 sublabel=None):
        self.label = label
        self.on_select = on_select
        self.on_adjust = on_adjust
        self.value = value        # callable -> str (right-aligned)
        self.marker = marker      # callable -> bool (current → yellow tile frame)
        self.bar = bar            # callable -> 0..1 (inline VU bar)
        self.submenu = submenu
        self.color = color        # tile color override (else palette by index)
        self.sublabel = sublabel  # callable -> str|None (2nd line on a tile, e.g. preset name)


class MenuScreen:
    """A screen: title + items, rendered as a Metro tile grid (paged) or a
    tabular list. Navigation/render/input treat every screen uniformly."""

    def __init__(self, title, items, idx=0, tiles=False, footer=None):
        self.title = title
        self.items = items
        self.idx = idx
        self.tiles = tiles
        self.page = 0
        self.footer = footer          # optional one-line status under the list

    @property
    def selected(self):
        return self.items[self.idx]

    def move(self, delta):
        self.idx = max(0, min(len(self.items) - 1, self.idx + delta))

    # ---- pagination (tiles: PAGE_TILES per page; lists: LIST_ROWS per page, #276) ----
    def _per_page(self):
        return PAGE_TILES if self.tiles else LIST_ROWS

    def npages(self):
        if not self.items:
            return 1
        per = self._per_page()
        return max(1, (len(self.items) + per - 1) // per)

    def page_slice(self):
        """[(global_index, item), ...] for the current page."""
        per = self._per_page()
        self.page %= self.npages()
        start = self.page * per
        return [(start + i, it) for i, it in enumerate(self.items[start:start + per])]

    def page_flip(self, delta=1):
        n = self.npages()
        self.page = (self.page + delta) % n


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


def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(d):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(d, f)


def list_audio_cards():
    """[(name, label), ...] of ALSA cards that expose PCM playback (#282).
    `name` is the bracketed card id used as plughw:NAME — same token start-piano.sh
    persists/reads; `label` is a friendlier model name for the menu. MIDI-only
    devices (the Keystation) have no playback PCM and are skipped."""
    cards = []
    try:
        text = open("/proc/asound/cards").read()
    except OSError:
        return cards
    for m in re.finditer(r"^\s*(\d+)\s+\[([^\]]+)\]\s*:\s*(.*)$", text, re.M):
        idx, name, desc = m.group(1), m.group(2).strip(), m.group(3).strip()
        if not glob.glob(f"/proc/asound/card{idx}/pcm*p"):
            continue                               # no playback PCM (e.g. USB-MIDI)
        label = desc.split(" - ", 1)[-1].strip() or name   # "USB-Audio - M-Track Hub" -> "M-Track Hub"
        cards.append((name, label))
    return cards


def sf_key(path):
    """Stable identity of a soundfont across synth reloads = its basename. Used to
    match a persisted/offline choice to a live fluidsynth font id (#276)."""
    return os.path.basename(path or "")


def list_soundfont_files():
    """[path, ...] of *.sf2/*.sf3 in SOUNDFONT_DIR, sorted by name — same set and
    order start-piano.sh loads into fluidsynth, so the catalog matches offline (#276)."""
    files = []
    try:
        for name in os.listdir(SOUNDFONT_DIR):
            if name.lower().endswith((".sf2", ".sf3")):
                files.append(os.path.join(SOUNDFONT_DIR, name))
    except OSError:
        return []
    return sorted(files)


def read_sf_presets(path):
    """[(bank, prog, name), ...] read straight from a SoundFont's `phdr` chunk —
    no synth, no audio decode, no hardware (#276). Works for SF2 AND SF3 (only the
    sample data differs in SF3; pdta/phdr is identical). Same shape as Fluid.presets."""
    try:
        with open(path, "rb") as f:
            riff = f.read(12)
            if riff[:4] != b"RIFF" or riff[8:12] != b"sfbk":
                return []
            end, pos, phdr = struct.unpack("<I", riff[4:8])[0] + 8, 12, None
            while pos < end:
                f.seek(pos)
                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                cid, csz = hdr[:4], struct.unpack("<I", hdr[4:8])[0]
                if cid == b"LIST" and f.read(4) == b"pdta":
                    spos, send = pos + 12, pos + 8 + csz
                    while spos < send:
                        f.seek(spos)
                        sh = f.read(8)
                        if len(sh) < 8:
                            break
                        sid, ssz = sh[:4], struct.unpack("<I", sh[4:8])[0]
                        if sid == b"phdr":
                            f.seek(spos + 8)
                            phdr = f.read(ssz)
                            break
                        spos += 8 + ssz + (ssz & 1)
                    break
                pos += 8 + csz + (csz & 1)
    except OSError:
        return []
    if not phdr:
        return []
    out = []
    for i in range(0, len(phdr) - 38, 38):             # drop the terminal EOP record
        rec = phdr[i:i + 38]
        name = rec[:20].split(b"\x00", 1)[0].decode("latin-1", "replace").strip()
        prog, bank = struct.unpack("<HH", rec[20:24])
        out.append((bank, prog, name))
    return sorted(out)


def board_model():
    """Board name from the device tree, e.g. 'Raspberry Pi 3 Model B Plus' (#289)."""
    try:
        with open("/proc/device-tree/model", "rb") as f:
            return f.read().rstrip(b"\x00").decode("utf-8", "replace").strip() or "?"
    except OSError:
        return "?"


def local_ip():
    """Best-effort primary IPv4 (the address you'd SSH to), '?' if offline (#289).
    Opening a UDP socket and connect() picks the source IP without sending anything."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 53))                   # TEST-NET-1: routable lookup, no packet sent
        return s.getsockname()[0]
    except OSError:
        return "?"
    finally:
        s.close()


class App:
    BAR_H = 45      # top bar = same height as a settings row (ROW_H)
    ROW_H = 45      # tabular rows

    def __init__(self):
        self.fb = Framebuffer(FB_DEV)
        global LIST_ROWS                            # rows that fit a list page on this screen (#276)
        LIST_ROWS = max(1, (self.fb.h - self.BAR_H) // self.ROW_H)
        self.fs = Fluid(FS_HOST, FS_PORT)
        self.touch = Touch()
        self.f_big = load_font(24)
        self.f_med = load_font(18)
        self.f_small = load_font(13)
        self.gain = 2.5
        self.fonts = []                 # [(sfid_or_None, path)] — sfid None when offline (disk)
        self.cur_font_path = None       # current soundfont path (identity = basename, #276)
        self.cur_bp = None              # current (bank, prog)
        # persisted settings (screen sleep #277, audio device #282, preset #276)
        self.bl = Backlight()
        s = load_settings()
        self.sleep_after = s.get("sleep_after", SLEEP_DEFAULT)
        self.soundcard = s.get("soundcard", "")     # "" = auto-detect (start-piano.sh)
        global PAGE_TILES                            # tiles per page, adjustable in Settings (#276)
        PAGE_TILES = int(s.get("page_tiles", PAGE_TILES))
        pr = s.get("preset")                        # last chosen preset, applied when synth is up
        self.cur_preset_name = ""
        if pr:
            self.cur_font_path = os.path.join(SOUNDFONT_DIR, pr["font"])
            self.cur_bp = (pr["bank"], pr["prog"])
            self.cur_preset_name = pr.get("name", "")
        self._online = False                        # last seen synth state (for apply-on-connect)
        self.stack = [self._home_menu()]
        cal = load_cal()
        if cal:
            self.touch.set_affine(cal)
        self.asleep = False
        self.last_active = time.monotonic()

    def _update_settings(self, **kw):
        """Merge keys into settings.json (load→update→save) so writing one key
        never clobbers the others (#282: soundcard + sleep_after coexist)."""
        d = load_settings()
        d.update(kw)
        save_settings(d)

    # ---- soundfont / preset model ----
    def refresh_fonts(self):
        """Build the Home catalog. Online: from fluidsynth `fonts` (sfid known).
        Offline: from the .sf2/.sf3 files on disk (sfid=None) so the two-level tile
        UI works with no synth/hardware (#276). Rebuild Home if it changed; apply a
        persisted preset the moment the synth comes online. Returns True if changed."""
        online = self.fs.online or self.fs.connect()
        fonts = self.fs.fonts() if online else []
        if not fonts:                                # offline, or synth up with nothing loaded yet
            fonts = [(None, p) for p in list_soundfont_files()]
        changed = fonts != self.fonts
        if changed:
            self.fonts = fonts
            if len(self.stack) == 1:                 # only swap when sitting on Home
                self.stack[0] = self._home_menu()
        if online and not self._online:              # offline -> online: re-apply the saved preset
            self._apply_preset()
        self._online = online
        return changed

    def _home_menu(self):
        items = []
        for sfid, path in self.fonts:
            items.append(Item(
                font_label(path),
                on_select=(lambda i=sfid, p=path: self._tap_font(i, p)),
                marker=(lambda p=path: sf_key(self.cur_font_path) == sf_key(p)),
                sublabel=(lambda p=path: self.cur_preset_name
                          if (self.cur_bp and sf_key(self.cur_font_path) == sf_key(p)) else None),
                submenu=True))
        if not items:
            items.append(Item("No soundfonts", color=TILE_MUTED))
        items.append(Item("Settings", on_select=self._open_settings,
                          submenu=True, color=TILE_SETTINGS))
        return MenuScreen("pisynth", items, tiles=True)

    def _preset_list(self, sfid, path):
        """Presets for a font: live from fluidsynth when loaded (sfid set), else
        straight from the .sf file on disk (#276)."""
        return self.fs.presets(sfid) if sfid is not None else read_sf_presets(path)

    def _default_preset(self, sfid, path):
        """The font's default preset (first of bank 0, else first overall), or None."""
        presets = self._preset_list(sfid, path)
        bank0 = [p for p in presets if p[0] == 0]
        presets = bank0 or presets
        return presets[0] if presets else None

    def _tap_font(self, sfid, path):
        """Home tile: two-step (#276). First tap on a font selects its DEFAULT preset
        (plays it, stays Home); tapping the SAME (already-current) font drills into its
        preset list."""
        if sf_key(self.cur_font_path) == sf_key(path):
            self._open_font(sfid, path)              # already current → enter preset list
        else:
            d = self._default_preset(sfid, path)     # first tap → select the default preset
            if d:
                self._choose_preset(path, d[0], d[1], d[2])

    def _open_font(self, sfid, path):
        presets = self._preset_list(sfid, path)
        bank0 = [p for p in presets if p[0] == 0]
        presets = bank0 or presets
        if not presets:
            return                                   # nothing to drill into
        items = []
        for bank, prog, name in presets:
            items.append(Item(
                name,
                on_select=(lambda pa=path, b=bank, p=prog, nm=name: self._choose_preset(pa, b, p, nm)),
                marker=(lambda pa=path, b=bank, p=prog:
                        sf_key(self.cur_font_path) == sf_key(pa) and self.cur_bp == (b, p))))
        self.stack.append(MenuScreen(font_label(path), items, tiles=True))

    def _choose_preset(self, path, bank, prog, name=""):
        """Select a preset by font PATH (sfid-independent). Persist the choice (incl.
        the preset NAME for the Home tile label) and apply it now if the synth is up;
        otherwise it applies when the synth starts."""
        self.cur_font_path, self.cur_bp, self.cur_preset_name = path, (bank, prog), name
        self._update_settings(preset={"font": sf_key(path), "bank": bank, "prog": prog, "name": name})
        self._apply_preset()

    def _sfid_for_path(self, path):
        """Resolve a font path to its live fluidsynth font id by basename, or None
        when the synth isn't running / hasn't loaded it."""
        for sfid, p in self.fs.fonts():
            if sf_key(p) == sf_key(path):
                return sfid
        return None

    def _apply_preset(self):
        """Push the current preset to fluidsynth if it's online. No-op offline —
        refresh_fonts re-applies it on the next offline->online transition (#276)."""
        if not (self.cur_font_path and self.cur_bp):
            return False
        sfid = self._sfid_for_path(self.cur_font_path)
        if sfid is None:
            return False
        self.fs.select(sfid, *self.cur_bp)
        return True

    def _settings_menu(self):
        # Categorized (#289): Audio · Display · Tools · Info.
        def push(mk):
            return lambda: self.stack.append(mk())
        return MenuScreen("Settings", [
            Item("Audio", on_select=push(self._audio_menu), submenu=True),
            Item("Display", on_select=push(self._display_menu), submenu=True),
            Item("Tools", on_select=push(self._tools_menu), submenu=True),
            Item("Info", on_select=push(self._info_menu), submenu=True),
        ])

    def _audio_menu(self):
        return MenuScreen("Audio", [
            Item("Gain", on_adjust=(lambda d: self._set_gain(self.gain + 0.5 * d)),
                 value=(lambda: f"{self.gain:.1f}"), bar=(lambda: self.gain / 10.0)),
            Item("Audio device", on_select=self._open_audio,
                 value=self._audio_label, submenu=True),
        ])

    def _display_menu(self):
        return MenuScreen("Display", [
            Item("Screen sleep", on_adjust=self._cycle_sleep, value=self._sleep_label),
            Item("Tiles per page", on_adjust=self._cycle_page_tiles,
                 value=(lambda: str(PAGE_TILES))),
            Item("Calibrate touchscreen", on_select=self.calibrate, submenu=True),
        ])

    def _tools_menu(self):
        return MenuScreen("Tools", [
            Item("Metronome", value=(lambda: "soon")),   # #287 lands here
        ])

    def _info_menu(self):
        # Snapshot the values once (cheap, avoids per-render file/socket reads).
        rows = [
            ("Version", VERSION),
            ("Board", board_model()),
            ("Kernel", os.uname().release),
            ("Screen", f"{self.fb.w}x{self.fb.h}"),
            ("Host", socket.gethostname()),
            ("IP", local_ip()),
            ("Soundfonts", str(len(self.fonts))),
        ]
        return MenuScreen("Info", [Item(k, value=(lambda v=v: v)) for k, v in rows])

    # ---- audio device picker (ticket #282) ----
    def _audio_label(self):
        """Friendly name of the configured card, or 'Auto' when unset."""
        if not self.soundcard:
            return "Auto"
        for name, label in list_audio_cards():
            if name == self.soundcard:
                return label
        return self.soundcard                      # configured but not currently present

    def _open_audio(self):
        items = [Item("Auto (detect USB)",
                      on_select=(lambda: self._choose_soundcard("")),
                      marker=(lambda: not self.soundcard))]
        for name, label in list_audio_cards():
            items.append(Item(
                label,
                on_select=(lambda n=name: self._choose_soundcard(n)),
                marker=(lambda n=name: self.soundcard == n)))
        self.stack.append(MenuScreen("Audio device", items))

    def _choose_soundcard(self, name):
        self.soundcard = name
        self._update_settings(soundcard=name)
        applied = self._restart_audio()
        if self.cur.title == "Audio device":
            self.cur.footer = "Restarting audio…" if applied else "Saved — applies on next restart"

    def _restart_audio(self):
        """Ask systemd to restart piano.service so the new device takes effect.
        Returns True if systemd accepted it (privilege present via migration 011),
        False otherwise — the choice is still persisted and start-piano.sh applies
        it on the next start. Non-blocking so the UI never freezes on the restart."""
        try:
            r = subprocess.run(["systemctl", "restart", "--no-block", "piano.service"],
                               capture_output=True, timeout=5)
            return r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    # ---- screen sleep (ticket #277) ----
    def _sleep_label(self):
        return dict(SLEEP_OPTIONS).get(self.sleep_after, f"{self.sleep_after}s")

    def _cycle_sleep(self, delta):
        vals = [s for s, _ in SLEEP_OPTIONS]
        i = vals.index(self.sleep_after) if self.sleep_after in vals else 0
        self.sleep_after = vals[(i + delta) % len(vals)]
        self._update_settings(sleep_after=self.sleep_after)
        self.last_active = time.monotonic()

    def _cycle_page_tiles(self, delta):
        """Settings → Tiles per page (#276): cycle PAGE_TILES through the presets,
        persist it, and reset paging so the change is visible immediately."""
        global PAGE_TILES
        opts = PAGE_TILES_OPTIONS
        i = opts.index(PAGE_TILES) if PAGE_TILES in opts else opts.index(6)
        PAGE_TILES = opts[(i + delta) % len(opts)]
        self._update_settings(page_tiles=PAGE_TILES)
        for m in self.stack:                         # clamp pages to the new count
            m.page = 0

    def sleep_screen(self):
        if self.asleep:
            return
        self.asleep = True
        self.fb.blit(Image.new("RGB", (self.fb.w, self.fb.h), (0, 0, 0)))
        self.bl.set(False)
        print("[pisynth-ui] screen sleep", flush=True)

    def wake_screen(self):
        self.last_active = time.monotonic()
        if not self.asleep:
            return
        self.asleep = False
        self.bl.set(True)
        self.render()
        print("[pisynth-ui] screen wake", flush=True)

    @property
    def cur(self):
        return self.stack[-1]

    def _set_gain(self, g):
        self.gain = max(0.0, min(10.0, round(g * 2) / 2))
        self.fs.set_gain(self.gain)

    def _open_settings(self):
        self.stack.append(self._settings_menu())

    # ---- navigation (touch / D-pad / socket all go through these) ----
    def nav_move(self, delta):
        self.cur.move(delta)
        per = PAGE_TILES if self.cur.tiles else LIST_ROWS   # keep the page in sync with the cursor
        self.cur.page = self.cur.idx // per
        self.render()

    def nav_select(self):
        it = self.cur.selected
        if it.on_select:
            it.on_select()
        self.render()

    def nav_adjust(self, delta):
        it = self.cur.selected
        if it.on_adjust:
            it.on_adjust(delta)
            self.render()

    def nav_back(self):
        if len(self.stack) > 1:
            self.stack.pop()
        self.render()

    def nav_page(self, delta=1):
        self.cur.page_flip(delta)
        self.render()

    def _back_rect(self):
        """Standardized back button (top-left of the bar) on every sub-screen."""
        return (0, 0, 56, self.BAR_H) if len(self.stack) > 1 else None

    def _page_rect(self):
        """Pagination hit zone (top-right of the bar) when the screen is paged.
        Left half = previous page, right half = next (matches the ‹ › arrows)."""
        return (self.fb.w - 110, 0, self.fb.w, self.BAR_H) if self.cur.npages() > 1 else None

    # ---- calibration ----
    def _center_text(self, d, y, text, font, fill=FG):
        tw = d.textlength(text, font=font)
        d.text((self.fb.w / 2 - tw / 2, y), text, font=font, fill=fill)

    def _tri(self, d, cx, cy, h, direction, fill):
        """Filled triangle drawn as horizontal scanlines so the diagonal steps evenly —
        a constant 1 px change per row (regular slope), pointing left/right. Deliberately
        not mathematically equilateral: equilateral gave uneven pixel steps (#289)."""
        cx, cy, hh = int(cx), int(cy), int(h) // 2
        xL = cx - hh // 2
        for i in range(-hh, hh + 1):
            depth = hh - abs(i)                  # constant 1 px/row → even slope
            y = cy + i
            if direction == "right":
                d.line((xL, y, xL + depth, y), fill=fill)
            else:
                d.line((xL + hh - depth, y, xL + hh, y), fill=fill)

    def _draw_target(self, tx, ty, n, total):
        img = Image.new("RGB", (self.fb.w, self.fb.h), BG)
        d = ImageDraw.Draw(img)
        self._center_text(d, 20, "Touch calibration", self.f_big, ACCENT)
        self._center_text(d, 54, f"Tap the target  {n}/{total}", self.f_med)
        tx, ty, r = int(tx), int(ty), 16
        d.line((tx - r, ty, tx + r, ty), fill=ACCENT, width=2)
        d.line((tx, ty - r, tx, ty + r), fill=ACCENT, width=2)
        d.ellipse((tx - r, ty - r, tx + r, ty + r), outline=ACCENT, width=2)
        d.ellipse((tx - 3, ty - 3, tx + 3, ty + 3), fill=OK)
        self.fb.blit(img)

    def calibrate(self):
        w, h, ins = self.fb.w, self.fb.h, 0.15
        targets = [(w * ins, h * ins), (w * (1 - ins), h * ins),
                   (w * (1 - ins), h * (1 - ins)), (w * ins, h * (1 - ins))]
        raws = []
        for i, (tx, ty) in enumerate(targets):
            self._draw_target(tx, ty, i + 1, len(targets))
            raws.append(self.touch.wait_raw_tap())
            time.sleep(0.35)
        coeffs = solve_affine(raws, targets)
        save_cal(coeffs)
        self.touch.set_affine(coeffs)
        print(f"[pisynth-ui] calibrated -> {CAL_PATH}: {coeffs}", flush=True)
        self._verify_loop()

    def _verify_loop(self):
        w, h = self.fb.w, self.fb.h
        bw, bh = 130, 54
        done = ((w - bw) // 2, (h - bh) // 2, (w + bw) // 2, (h + bh) // 2)
        rx = ry = None
        touching = False
        dot = None
        self._draw_verify(done, dot)
        for ev in self.touch.dev.read_loop():
            if ev.type == ecodes.EV_ABS:
                if ev.code == ecodes.ABS_X:
                    rx = ev.value
                elif ev.code == ecodes.ABS_Y:
                    ry = ev.value
                if touching and rx is not None and ry is not None and self.touch.affine:
                    dot = self.touch.map(rx, ry)
                    self._draw_verify(done, dot)
            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                if ev.value == 1:
                    touching = True
                elif ev.value == 0:
                    touching = False
                    if dot and done[0] <= dot[0] <= done[2] and done[1] <= dot[1] <= done[3]:
                        return
                    self._draw_verify(done, dot)

    def _draw_verify(self, done, dot):
        img = Image.new("RGB", (self.fb.w, self.fb.h), BG)
        d = ImageDraw.Draw(img)
        self._center_text(d, 14, "Calibration check", self.f_med, ACCENT)
        self._center_text(d, 38, "Touch to test, then Done", self.f_small)
        d.rounded_rectangle(done, radius=8, fill=(50, 110, 70), outline=ACCENT)
        lab = "Done"
        tw = d.textlength(lab, font=self.f_med)
        d.text(((done[0] + done[2]) / 2 - tw / 2, (done[1] + done[3]) / 2 - 12), lab, font=self.f_med, fill=FG)
        if dot:
            x, y = dot
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 80, 80), outline=FG)
            d.text((6, self.fb.h - 20), f"({x}, {y})", font=self.f_small, fill=FG)
        self.fb.blit(img)

    # ---- render ----
    def _hbar(self, d, x0, y0, x1, y1, frac):
        n, gap = 12, 2
        seg = (x1 - x0 - (n - 1) * gap) / n
        for k in range(n):
            f = (k + 0.5) / n
            base = (60, 200, 90) if f < 0.6 else (235, 200, 60) if f < 0.85 else (225, 80, 80)
            col = base if f <= frac else tuple(c // 6 for c in base)
            sx = x0 + k * (seg + gap)
            d.rectangle((sx, y0, sx + seg, y1), fill=col)

    def render(self):
        w, h = self.fb.w, self.fb.h
        img = Image.new("RGB", (w, h), BG)
        d = ImageDraw.Draw(img)
        m = self.cur
        # status / menu bar: back button (left) · title · pagination (right)
        d.rectangle((0, 0, w, self.BAR_H), fill=BARBG)
        cy = self.BAR_H // 2
        tx = 10
        back = self._back_rect()
        if back:
            self._tri(d, 22, cy, 20, "left", ACCENT)   # back arrow = pager-triangle design, own colour (#289)
            d.line((back[2], 6, back[2], self.BAR_H - 6), fill=(64, 68, 86), width=1)
            tx = back[2] + 8
        d.text((tx, cy - 10), m.title, font=self.f_med, fill=FG)
        npages = m.npages()
        if npages > 1:                              # ◀ p/N ▶ — yellow triangles around the number (#276)
            num = f"{m.page + 1}/{npages}"
            nw = d.textlength(num, font=self.f_med)
            tw, gap, right = 16, 10, w - 12
            self._tri(d, right - tw / 2, cy, 20, "right", SEL_BORDER)
            d.text((right - tw - gap - nw, cy - 10), num, font=self.f_med, fill=FG)
            self._tri(d, right - tw - gap - nw - gap - tw / 2, cy, 20, "left", SEL_BORDER)
        if m.tiles:
            self._draw_tiles(d, m)
        else:
            self._draw_rows(d, m)
        if m.footer:
            fw = d.textlength(m.footer, font=self.f_small)
            d.text((w / 2 - fw / 2, h - 18), m.footer, font=self.f_small, fill=MUTED)
        self.fb.blit(img)

    # ---- list screens ----
    def _row_y(self, i):
        return self.BAR_H + 4 + i * self.ROW_H

    def _stepper_rects(self, ry):
        """(minus, plus, value_center_x) for an adjustable row (e.g. Gain)."""
        cy = ry + self.ROW_H // 2
        b = self.ROW_H - 12
        plus = (self.fb.w - 10 - b, cy - b // 2, self.fb.w - 10, cy + b // 2)
        vcx = plus[0] - 26
        mx1 = plus[0] - 52
        minus = (mx1 - b, cy - b // 2, mx1, cy + b // 2)
        return minus, plus, vcx

    def _draw_rows(self, d, m):
        w = self.fb.w
        for pos, (gi, it) in enumerate(m.page_slice()):   # paged (#276)
            ry = self._row_y(pos)
            cy = ry + self.ROW_H // 2
            if gi == m.idx:
                d.rectangle((0, ry, w, ry + self.ROW_H - 2), fill=SELBG)
                d.rectangle((0, ry, 3, ry + self.ROW_H - 2), fill=ACCENT)
            if it.marker and it.marker():
                d.ellipse((14, cy - 4, 22, cy + 4), fill=OK)
            d.text((30, cy - 10), it.label, font=self.f_med, fill=FG)
            if it.on_adjust:                       # − value + stepper
                minus, plus, vcx = self._stepper_rects(ry)
                for rect, sym in ((minus, "−"), (plus, "+")):
                    d.rounded_rectangle(rect, radius=6, fill=BTN, outline=ACCENT)
                    sw = d.textlength(sym, font=self.f_med)
                    d.text(((rect[0] + rect[2]) / 2 - sw / 2, (rect[1] + rect[3]) / 2 - 11),
                           sym, font=self.f_med, fill=FG)
                if it.value:
                    v = it.value()
                    vw = d.textlength(v, font=self.f_med)
                    d.text((vcx - vw / 2, cy - 10), v, font=self.f_med, fill=ACCENT)
                if it.bar:
                    self._hbar(d, 130, cy - 5, minus[0] - 12, cy + 5, it.bar())
            else:
                rx = w - 14
                if it.submenu:
                    d.text((rx - 10, cy - 11), "›", font=self.f_med, fill=MUTED)
                    rx -= 22
                if it.value:
                    v = it.value()
                    vw = d.textlength(v, font=self.f_med)
                    d.text((rx - vw, cy - 10), v, font=self.f_med, fill=ACCENT)

    # ---- tile screen (home + presets) ----
    def _tile_grid(self, n, cols=3, rows=None):
        gap = 6
        w, h = self.fb.w, self.fb.h
        top = self.BAR_H + gap
        if rows is None:
            rows = max(1, (n + cols - 1) // cols)
        tw = (w - gap * (cols + 1)) / cols
        th = (h - top - gap * rows) / rows
        rects = []
        for idx in range(n):
            r, c = divmod(idx, cols)
            x0 = gap + c * (tw + gap)
            y0 = top + r * (th + gap)
            rects.append((x0, y0, x0 + tw, y0 + th))
        return rects

    def _fixed_rows(self, m):
        """Keep a uniform tile size across pages: 3 rows once a screen is paged."""
        return ((PAGE_TILES + 2) // 3) if m.npages() > 1 else None

    def _draw_tiles(self, d, m):
        slice_ = m.page_slice()
        rects = self._tile_grid(len(slice_), rows=self._fixed_rows(m))
        for (gi, it), rect in zip(slice_, rects):
            col = it.color or TILE_PALETTE[gi % len(TILE_PALETTE)]
            d.rectangle(rect, fill=col)            # flat tile
            sub = it.sublabel() if it.sublabel else None
            self._tile_label(d, rect, it.label, sub)
            if it.marker and it.marker():          # current selection → yellow OUTER frame (#290)
                b = 3                              # ring sits in the inter-tile gap, outside the tile
                d.rectangle((rect[0] - b, rect[1] - b, rect[2] + b, rect[3] + b),
                            outline=SEL_BORDER, width=b)

    def _tile_label(self, d, rect, label, sub=None):
        x0, y0, x1, y1 = rect
        maxw = (x1 - x0) - 12
        words, lines, cur = label.split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if d.textlength(t, font=self.f_med) <= maxw:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        lh = 21
        sub_h = 17 if sub else 0
        ty = (y0 + y1) / 2 - (lh * len(lines) + sub_h) / 2
        for ln in lines:
            tw = d.textlength(ln, font=self.f_med)
            d.text(((x0 + x1) / 2 - tw / 2, ty), ln, font=self.f_med, fill=(255, 255, 255))
            ty += lh
        if sub:                                    # 2nd line: selected preset name (#276)
            s = self._ellipsize(d, sub, self.f_small, maxw)
            tw = d.textlength(s, font=self.f_small)
            d.text(((x0 + x1) / 2 - tw / 2, ty + 1), s, font=self.f_small, fill=SEL_SUB)

    def _ellipsize(self, d, text, font, maxw):
        if d.textlength(text, font=font) <= maxw:
            return text
        while text and d.textlength(text + "…", font=font) > maxw:
            text = text[:-1]
        return (text + "…") if text else ""

    # ---- input ----
    def handle_tap(self, x, y):
        if y < self.BAR_H:                        # bar: back (left) / page (right)
            back = self._back_rect()
            page = self._page_rect()
            if back and back[0] <= x <= back[2]:
                self.nav_back()
            elif page and page[0] <= x <= page[2]:
                self.nav_page(-1 if x < (page[0] + page[2]) / 2 else 1)
            return
        if self.cur.tiles:
            self._hit_tiles(x, y)
        else:
            self._hit_list(x, y)

    def _hit_list(self, x, y):
        m = self.cur
        pos = (y - (self.BAR_H + 4)) // self.ROW_H
        slice_ = m.page_slice()
        if not (0 <= pos < len(slice_)):
            return
        gi, it = slice_[pos]
        m.idx = gi
        if it.on_adjust:                          # − / + stepper buttons
            minus, plus, _ = self._stepper_rects(self._row_y(pos))
            if minus[0] <= x <= minus[2] and minus[1] <= y <= minus[3]:
                self.nav_adjust(-1)
            elif plus[0] <= x <= plus[2] and plus[1] <= y <= plus[3]:
                self.nav_adjust(1)
            else:
                self.render()                     # just move the cursor
        else:
            self.nav_select()

    def _hit_tiles(self, x, y):
        slice_ = self.cur.page_slice()
        for (gi, _), rect in zip(slice_, self._tile_grid(len(slice_), rows=self._fixed_rows(self.cur))):
            if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                self.cur.idx = gi
                self.nav_select()
                return

    # ---- preset cycling (D-pad / socket) ----
    def _cycle_preset(self, delta):
        """Step through the current soundfont's presets (or the first font's)."""
        path = self.cur_font_path or (self.fonts[0][1] if self.fonts else None)
        if path is None:
            return
        presets = self._preset_list(self._sfid_for_path(path), path)
        bank0 = [p for p in presets if p[0] == 0]
        presets = bank0 or presets
        if not presets:
            return
        keys = [(b, p) for b, p, _ in presets]
        i = keys.index(self.cur_bp) if self.cur_bp in keys else -1
        b, p = keys[(i + delta) % len(keys)]
        name = next((n for bb, pp, n in presets if (bb, pp) == (b, p)), "")
        self._choose_preset(path, b, p, name)

    def dispatch(self, line):
        parts = line.split()
        if not parts:
            return "empty"
        cmd = parts[0]
        if cmd in ("menu", "action", "tap"):          # interactive → wake first
            self.last_active = time.monotonic()
            if self.asleep:
                self.wake_screen()
                if cmd == "tap":
                    return "ok"                       # consume the wake tap
        if cmd == "state":
            bp = f"{self.cur_bp[0]}:{self.cur_bp[1]}" if self.cur_bp else "-"
            return (f"screen={self.cur.title!r} idx={self.cur.idx} "
                    f"page={self.cur.page + 1}/{self.cur.npages()} "
                    f"fonts={len(self.fonts)} cur_font={sf_key(self.cur_font_path) or '-'} preset={bp} "
                    f"gain={self.gain} soundcard={self.soundcard or 'auto'} "
                    f"asleep={int(self.asleep)} sleep_after={self.sleep_after} "
                    f"online={int(self.fs.online or self.fs.connect())} "
                    f"render={RENDER_MODE} "
                    f"calibrated={int(self.touch.affine is not None)}")
        if cmd == "render":
            self.render()
            return "ok"
        if cmd == "sleep":
            self.sleep_screen()
            return "ok"
        if cmd == "wake":
            self.wake_screen()
            return "ok"
        if cmd == "refresh":
            self.refresh_fonts()
            self.render()
            return "ok"
        if cmd == "menu" and len(parts) > 1:
            sub = parts[1]
            if sub == "up":
                self.nav_move(-1)
            elif sub == "down":
                self.nav_move(1)
            elif sub == "select":
                self.nav_select()
            elif sub == "back":
                self.nav_back()
            elif sub == "page":
                self.nav_page(1)
            elif sub == "adjust" and len(parts) > 2:
                self.nav_adjust(int(parts[2]))
            else:
                return f"unknown menu: {sub}"
            return "ok"
        if cmd == "calibrate":
            self.calibrate()
            self.render()
            return "ok"
        if cmd == "settings":
            self._open_settings()
            self.render()
            return "ok"
        if cmd == "action" and len(parts) > 1:
            acts = {
                "next_preset": lambda: self._cycle_preset(1),
                "prev_preset": lambda: self._cycle_preset(-1),
                "gain_up": lambda: self._set_gain(self.gain + 0.5),
                "gain_down": lambda: self._set_gain(self.gain - 0.5),
            }
            fn = acts.get(parts[1])
            if fn:
                fn()
                self.render()
                return "ok"
            return f"unknown action: {parts[1]}"
        if cmd == "tap" and len(parts) >= 3:
            self.handle_tap(int(parts[1]), int(parts[2]))
            return "ok"
        return f"unknown: {line}"

    def _control_server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", CTL_PORT))
        s.listen(4)
        s.setblocking(False)
        return s

    def run(self):
        print(f"[pisynth-ui] {self.fb.w}x{self.fb.h} on {FB_DEV}; render={RENDER_MODE}; "
              f"control on :{CTL_PORT}", flush=True)
        if self.touch.affine is None:
            print("[pisynth-ui] no calibration -> entering calibration", flush=True)
            self.calibrate()
        self.refresh_fonts()
        self.render()
        sel = selectors.DefaultSelector()
        sel.register(self.touch.fileno(), selectors.EVENT_READ, "touch")
        srv = self._control_server()
        sel.register(srv, selectors.EVENT_READ, "ctl")
        while True:
            events = sel.select(timeout=2.0)
            now = time.monotonic()
            if not events:                             # idle tick
                changed = self.refresh_fonts()         # also applies saved preset on connect
                if changed and not self.asleep:
                    self.render()
                if (not self.asleep and self.sleep_after
                        and now - self.last_active >= self.sleep_after):
                    self.sleep_screen()
                continue
            for key, _ in events:
                if key.data == "touch":
                    taps = self.touch.read_taps()
                    if not taps:
                        continue
                    self.last_active = now
                    if self.asleep:
                        self.wake_screen()             # first touch only wakes
                    else:
                        for x, y in taps:
                            self.handle_tap(x, y)
                elif key.data == "ctl":
                    try:
                        conn, _ = srv.accept()
                    except OSError:
                        continue
                    with conn:
                        conn.settimeout(1.0)
                        try:
                            data = conn.recv(256).decode(errors="ignore").strip()
                            conn.sendall((self.dispatch(data) + "\n").encode())
                        except OSError:
                            pass


if __name__ == "__main__":
    while True:
        try:
            App().run()
        except Exception as e:                       # keep the appliance alive
            print(f"[pisynth-ui] error: {e}", file=sys.stderr, flush=True)
            time.sleep(2)
