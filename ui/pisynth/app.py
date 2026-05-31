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
import os
import selectors
import socket
import subprocess
import sys
import threading
import time

from PIL import Image
from evdev import ecodes                            # io/ owns the device handles (#308)

FB_DEV   = os.environ.get("PISYNTH_FB", "/dev/fb0")
FS_HOST  = os.environ.get("FS_HOST", "127.0.0.1")
FS_PORT  = int(os.environ.get("FS_PORT", "9800"))
CTL_PORT = int(os.environ.get("PISYNTH_CTL_PORT", "9810"))
DEBUG    = os.environ.get("PISYNTH_DEBUG") == "1"
# Framebuffer paint strategy (#284). "full" = rewrite the whole RGB565 frame every
# render (simple, what we shipped). "partial" = write only the changed row band,
# and skip the write entirely when nothing changed — far less traffic on the slow
# SPI panel (~16-32 MHz). Set PISYNTH_RENDER=partial in pisynth-ui.service to switch.
RENDER_MODE = os.environ.get("PISYNTH_RENDER", "full")
VERSION  = "0.4.0"

# Keyboard channels we broadcast preset changes to. Channel 15 is left alone
# (midi-bridge.sh reserves it for the D-pad feedback SFX); channel 9 is reserved for the
# fused-metronome click (GM drum channel, #655) so the piano never plays on it.
KBD_CHANNELS = [c for c in range(15) if c != 9]

# Default click soundfont for the fused metronome (#655): the small GM font from apt
# `timgm6mb-soundfont` (~6 MB, already sideloaded by install-soundfonts.sh) — it carries
# the GM drum kit (bank 128) with the wood-block, so no extra asset/download is needed.
METRO_CLICK_SF_DEFAULT = "06-TimGM6mb.sf2"

# Screen-sleep delays offered in Settings (ticket #277). 0 = never sleep.
SLEEP_OPTIONS = [(0, "Off"), (30, "30s"), (60, "1m"), (120, "2m"), (300, "5m"), (600, "10m")]
# Off by default — auto-blanking surprised the user (#281). Opt in via Settings.
SLEEP_DEFAULT = 0


# Presentation toolkit (#308): menu SDK + the Renderer (the display/view layer). The
# palette/fonts now live entirely on the Renderer; the controller only needs the menu
# model, the renderer, and the one tile colour it sets directly.
from .ui.menu import Item, MenuScreen, PAGE_TILES_OPTIONS
from .ui.renderer import MidiState, Renderer, Status
from .ui.theme import TILE_MUTED

# Per-feature controller mixins (#308): audio / bluetooth / metronome screens + handlers.
from .screens import AudioMixin, BluetoothMixin, MetronomeMixin, NavMixin


# Hardware / device-backend adapters live in the io/ layer (#308). Re-exported
# here so the rest of app.py — and preview.py's monkeypatches — keep using the
# bare names (Framebuffer, Fluid, Bluetooth, ...).
from .io import (Backlight, Bluetooth, Fluid, Framebuffer, Metronome, MidiMonitor,
                 Touch, bt_any_connected)


# Domain / pure-logic layer (#308). Re-exported into app's namespace so existing
# call sites — and preview.py's monkeypatches (list_audio_cards / read_sf_presets
# / ...) — keep working on the bare names.
from .core.audio import (GAIN_DEFAULT, GAIN_MAX, GAIN_MIN, GAIN_STEP, audio_active,
                         audio_output_present, fluid_seq_port, list_midi_inputs,
                         metro_click_argv, midi_input_present, play_test)
from .core.geometry import solve_affine
from .core.settings import (CAL_PATH, SETTINGS_PATH, _legacy_json_path, load_cal,
                            load_settings, save_cal, save_settings)
from .core.soundfonts import (SOUNDFONT_DIR, font_label, list_soundfont_files,
                              read_sf_presets, sf_key)
from .core.system import (board_model, cpu_clock, cpu_temp, disk_info, health,
                          local_ip, mem_info, os_pretty, power_status, uptime_str)



class App(AudioMixin, BluetoothMixin, MetronomeMixin, NavMixin):
    def __init__(self):
        self.fb = Framebuffer(FB_DEV, RENDER_MODE == "partial")   # io adapter (#308)
        self.view = Renderer(self.fb)             # the display/view layer (#308 step 5)
        # rows that fit a list page on this screen (#276) — MenuScreen reads this (#308)
        MenuScreen.per_page_rows = max(1, (self.fb.h - self.view.BAR_H) // self.view.ROW_H)
        self.fs = Fluid(FS_HOST, FS_PORT, KBD_CHANNELS)           # io adapter (#308)
        self.touch = Touch()
        self.gain = GAIN_DEFAULT
        self.volume = None              # cached output volume %; read on opening Audio (#314)
        self._restart_pending = 0.0     # monotonic start of an audio restart; 0 = none (#282)
        self._health = "good"           # Home health smiley state: good|warn|crit (#325)
        self._health_t0 = 0.0           # last health recompute (its own slow throttle)
        self._toast_msg = ""            # transient toast overlay text (#320)
        self._toast_until = 0.0         # monotonic expiry of the toast; 0 = none (#320)
        self._hold_delta = 0            # +/- stepper currently held for auto-repeat (#314)
        self._hold_next = 0.0           # monotonic time of the next repeat
        self._hold_fired = False        # a repeat fired → swallow the release tap
        self.fonts = []                 # [(sfid_or_None, path)] — sfid None when offline (disk)
        self._loading = False           # a soundfont swap is in progress → amber tile frame (#334)
        self._load_thread = None        # background font-load thread, or None (#375)
        self._load_result = None        # (path, bp, sfid) posted by the worker when done (#375)
        self._load_fs = None            # dedicated fluidsynth connection for the load worker (#375)
        self._load_frame = 0            # spinner animation counter while loading (#375)
        self._load_phase = 0            # 0=idle, 1=loading font, 2=loading samples (#375 2-colour)
        self.cur_font_path = None       # current soundfont path (identity = basename, #276)
        self.cur_bp = None              # current (bank, prog)
        # persisted settings (screen sleep #277, audio device #282, preset #276)
        self.bl = Backlight()
        s = load_settings()
        self.sleep_after = s.get("sleep_after", SLEEP_DEFAULT)
        self.soundcard = s.get("soundcard", "")     # "" = auto-detect (start-piano.sh)
        # tiles per page, adjustable in Settings (#276) — held on MenuScreen (#308)
        MenuScreen.per_page_tiles = int(s.get("page_tiles", MenuScreen.per_page_tiles))
        pr = s.get("preset")                        # last chosen preset, applied when synth is up
        self.cur_preset_name = ""
        if pr:
            self.cur_font_path = os.path.join(SOUNDFONT_DIR, pr["font"])
            self.cur_bp = (pr["bank"], pr["prog"])
            self.cur_preset_name = pr.get("name", "")
        self._online = False                        # last seen synth state (for apply-on-connect)
        # Home top-bar status indicators (#306): cached so render() never shells out.
        # Polled (rfkill / /dev/snd glob) off the idle tick, throttled by _st_t0.
        self._st_wifi = False                        # Wi-Fi radio on (rfkill not soft-blocked)
        self._st_bt = False                          # Bluetooth radio on
        self._st_bt_conn = False                     # a Bluetooth device is connected (#306)
        self._st_midi = False                        # a USB-MIDI keyboard is plugged in
        self._st_audio = False                       # a usable sound card is present → audio icon (#327)
        self._st_t0 = 0.0                            # last poll time (monotonic)
        self.bt = Bluetooth()                        # Bluetooth pairing manager (#287)
        self._bt_scan = False
        self._bt_scan_t0 = 0.0                        # scan start time, for auto-off (#298)
        self.bt_names = dict((s.get("bluetooth") or {}).get("known") or {})  # mac->name, persisted (#301)
        self._bt_names_dirty = False
        self.bt_sink = (s.get("bluetooth") or {}).get("audio_sink", "")  # MAC of the BT audio output, or "" (#301)
        self.midi_keyboard = s.get("midi_keyboard", "")   # chosen MIDI keyboard name; "" = auto (all) (#326)
        self.midimon = MidiMonitor()                 # MIDI test-keyboard reader (#331)
        self._nav_init(s)                            # MIDI navigation: cfg + its own monitor (#373)
        self.metro = Metronome()                     # background metronome (#287/#655/#668)
        _m = s.get("metro", {})
        self.metro.bpm = _m.get("bpm", 100)
        self.metro.beats = _m.get("beats", 4)
        self.metro.vol = _m.get("vol", 80)          # metronome click volume 0-100 → SMF velocity (#655)
        self.metro.home_pulse = _m.get("home_pulse", False)   # pulse the Home metronome icon (#668)
        # The click always plays through the piano synth (#655/#668: no separate output). The
        # SMF is sent to fluidsynth via aplaymidi; `port` is its ALSA-seq target from fluid_setup.
        self.metro.click_cmd = lambda midi, port: metro_click_argv(midi, port)
        self.metro.fluid_setup = self._metro_fluid_setup       # load click font on ch9 → seq port
        self.metro.fluid_teardown = self._metro_fluid_teardown
        self.stack = [self._home_menu()]
        cal = load_cal()
        if cal:
            self.touch.set_affine(cal)
        self.asleep = False
        self.last_active = time.monotonic()

    def _update_settings(self, **kw):
        """Merge keys into settings.yaml (load→update→save) so writing one key
        never clobbers the others (#282: soundcard + sleep_after coexist)."""
        d = load_settings()
        d.update(kw)
        save_settings(d)

    def _remember_bt_name(self, mac, label):
        """Cache a device's friendly name for cross-session display (#301/#308 dedup).
        Shared by the audio/metronome/bluetooth screens (resolved via the MRO)."""
        if label and label != mac and self.bt_names.get(mac) != label:
            self.bt_names[mac] = label
            self._bt_names_dirty = True

    # ---- soundfont / preset model ----
    def refresh_fonts(self):
        """Build the Home catalog. Online: from fluidsynth `fonts` (sfid known).
        Offline: from the .sf2/.sf3 files on disk (sfid=None) so the two-level tile
        UI works with no synth/hardware (#276). Rebuild Home if it changed; apply a
        persisted preset the moment the synth comes online. Returns True if changed."""
        online = self.fs.online or self.fs.connect()
        # Catalog always from disk: a single soundfont is resident at a time (#334), so
        # fluidsynth's loaded list isn't the catalog — all fonts stay visible as tiles,
        # the chosen one is loaded on demand. Presets come from the .sf files (read_sf_presets).
        fonts = [(None, p) for p in list_soundfont_files()]
        changed = fonts != self.fonts
        if changed:
            self.fonts = fonts
            if len(self.stack) == 1:                 # only swap when sitting on Home
                self.stack[0] = self._home_menu()
        if online and not self._online:              # offline -> online: re-apply the saved preset
            self._apply_preset()
            self._nav_on_synth_online()              # re-silence the nav port (autoconnect race, #373)
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
        # Settings is reached via the cog in the Home top bar (#289), not a tile.
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
                on_select=(lambda pa=path, b=bank, p=prog, nm=name: self._tap_preset(pa, b, p, nm)),
                marker=(lambda pa=path, b=bank, p=prog:
                        sf_key(self.cur_font_path) == sf_key(pa) and self.cur_bp == (b, p))))
        self.stack.append(MenuScreen(font_label(path), items, tiles=True))

    def _tap_preset(self, path, bank, prog, name):
        """Tap a preset → select it. Re-tap the one already selected → leave the submenu
        (mirrors the two-tap font tile, #334)."""
        if sf_key(self.cur_font_path) == sf_key(path) and self.cur_bp == (bank, prog):
            self.nav_back()
        else:
            self._choose_preset(path, bank, prog, name)

    def _choose_preset(self, path, bank, prog, name=""):
        """Select a preset by font PATH (sfid-independent). Persist the choice (incl.
        the preset NAME for the Home tile label) and apply it now if the synth is up;
        otherwise it applies when the synth starts."""
        self.cur_font_path, self.cur_bp, self.cur_preset_name = path, (bank, prog), name
        self._update_settings(preset={"font": sf_key(path), "bank": bank, "prog": prog, "name": name})
        self._apply_preset()

    def _sfid_for_path(self, path, fs=None):
        """Resolve a font path to its live fluidsynth font id by basename, or None when
        the synth isn't running / hasn't loaded it. `fs` lets the load worker query on its
        own connection (#375)."""
        for sfid, p in (fs or self.fs).fonts():
            if sf_key(p) == sf_key(path):
                return sfid
        return None

    def _apply_preset(self):
        """Push the current preset to fluidsynth. ALWAYS done in the BACKGROUND (#375):
        with synth.dynamic-sample-loading=1 (#334) there are TWO slow phases — `load` (font
        structure) and `select` (the preset's samples, loaded on demand) — so even an
        already-loaded font needs a (phase-2) wait before sound works. The worker runs both;
        the indicator stays up across them. No-op offline; refresh_fonts re-applies on the
        next offline->online transition."""
        if not (self.cur_font_path and self.cur_bp):
            return False
        if self._loading:                            # a load is already running (#375)
            return False
        if not (self.fs.online or self.fs.connect()):
            return False
        loaded = self._sfid_for_path(self.cur_font_path) is not None
        self._start_load(self.cur_font_path, self.cur_bp, loaded)
        return True

    # ---- async soundfont loading (#375): load (phase 1) + select/samples (phase 2) ----
    def _load_conn(self):
        """A dedicated fluidsynth connection for the load worker so it never shares the
        socket with the UI thread (#375)."""
        if self._load_fs is None:
            self._load_fs = Fluid(FS_HOST, FS_PORT, KBD_CHANNELS)
        return self._load_fs

    def _start_load(self, path, bp, loaded):
        self._loading = True
        self._load_frame = 0
        self._load_result = None
        self._load_phase = 2 if loaded else 1        # already loaded → straight to the samples phase
        self.render()                                # show the indicator immediately
        self._load_thread = threading.Thread(target=self._load_worker, args=(path, bp), daemon=True)
        self._load_thread.start()

    def _load_keep(self, path):
        """Soundfont keys the unload sweep must SPARE: the piano target (#334 keeps one), plus
        the light metronome click font so it stays resident across preset changes (david:
        « garder la soundfont légère du métronome ») (#655)."""
        keep = {sf_key(path)}
        keep.add(sf_key(self._click_sf_path()))      # realpath → matches loaded basename (#655)
        return keep

    def _load_worker(self, path, bp):
        """Background, on a dedicated connection. Phase 1: load the font structure if it
        isn't resident (unload the previous one — single font in RAM, #334). Phase 2: select
        the preset, which makes fluidsynth load its samples on demand, then WAIT for that to
        finish — fluidsynth serialises shell commands, so a `fonts` query right after the
        select only replies once the samples are in. The load/select are global synth state,
        so the keyboard then plays through them. Posts the outcome to _load_result (#375)."""
        fs = self._load_conn()
        sfid = None
        keep = self._load_keep(path)                 # fonts to spare from the unload sweep (#334/#655)
        try:
            sfid = self._sfid_for_path(path, fs)
            if sfid is None:                         # phase 1 — load the font structure
                self._load_phase = 1
                for oid, p in fs.fonts():
                    if sf_key(p) not in keep:        # never unload the target (boot race vs start-piano, #378)
                        fs.unload(oid)
                sfid = self._sfid_for_path(path, fs) or fs.load(path)  # maybe it was there after all
            if sfid is not None:                     # phase 2 — keep ONE font (#334), select → samples on demand
                self._load_phase = 2
                self._load_frame = 0
                for oid, p in fs.fonts():
                    if sf_key(p) not in keep:
                        fs.unload(oid)
                sfid = self._sfid_for_path(path, fs)  # re-derive: only ever select a font that IS loaded —
                if sfid is not None:                  # never `select <missing id>` (#378: "No SoundFont id=2")
                    fs.select(sfid, *bp)
                    fs.fonts(overall=45)             # serialised → returns once samples are loaded
        except OSError:
            sfid = None
        self._load_result = (path, bp, sfid)

    def _finish_load(self):
        """Run-loop side of an async load (#375): the worker already loaded + selected, so
        here we only clear the indicator (sound is ready) — or, if the user picked a different
        preset while it ran, kick off the new one."""
        path, bp, sfid = self._load_result
        self._load_result = None
        self._load_thread = None
        self._loading = False
        self._load_phase = 0
        if (path, bp) != (self.cur_font_path, self.cur_bp):
            self._apply_preset()                     # target changed mid-load → apply the new one
            return
        if sfid is None:
            self.toast("load failed")
        self.render()                                # frame back to green (ready) now

    # ---- piano-output metronome: click played BY the main fluidsynth (#655/#668) ----
    def _click_sf_path(self):
        """Absolute REAL path of the click soundfont (the light default TimGM6mb), symlinks
        resolved (#655/#668). fluidsynth reports the resolved basename, so we match on the
        real path everywhere (load id lookup + the loader keep-set), or the click is never
        found/kept. The `~/soundfonts/06-…` symlink may be absent (install-soundfonts.sh not
        re-run) → fall back to the apt path so the metronome works out of the box."""
        for cand in (os.path.join(SOUNDFONT_DIR, METRO_CLICK_SF_DEFAULT),
                     "/usr/share/sounds/sf2/TimGM6mb.sf2"):     # apt timgm6mb-soundfont
            real = os.path.realpath(cand)
            if os.path.exists(real):
                return real
        return os.path.realpath(os.path.join(SOUNDFONT_DIR, METRO_CLICK_SF_DEFAULT))

    def _metro_fluid_setup(self):
        """Make the click playable by the MAIN fluidsynth (piano output, device ""): load its
        (light) soundfont and select a GM drum kit (bank 128) on the reserved channel 9, so
        aplaymidi's notes 76/77 sound as a woodblock mixed with the piano on the same card.
        Returns the synth's ALSA-seq port (for aplaymidi), or "" on failure (#655/#668)."""
        if not (self.fs.online or self.fs.connect()):
            return ""
        path = self._click_sf_path()
        if not os.path.exists(path):
            return ""
        sfid = self._sfid_for_path(path) or self.fs.load(path)   # loader spares it after (#655)
        if sfid is None:
            return ""
        self.fs.select_one(9, sfid, 128, 0)          # GM standard drum kit on the click channel
        return fluid_seq_port()                      # aplaymidi target into the piano synth

    def _metro_fluid_teardown(self):
        """Silence the click channel when the fused metronome stops (#655). The light font
        stays resident (spared by the loader) — only kill any sounding note on ch9."""
        if self.fs.online:
            self.fs.send("cc 9 123 0")               # all-notes-off on the click channel

    def _settings_menu(self):
        # Categorized (#289): Audio · Display · Tools · Info.
        def push(mk):
            return lambda: self.stack.append(mk())
        return MenuScreen("Settings", [
            Item("Tools", on_select=push(self._tools_menu), submenu=True),   # first — most used (david)
            Item("Audio", on_select=push(self._audio_menu), submenu=True),
            Item("MIDI", on_select=self._open_midi, value=self._midi_label, submenu=True),
            Item("Navigation", on_select=self._open_nav, submenu=True,
                 value=(lambda: "on" if self.nav_cfg["enabled"] else "off")),    # MIDI nav (#373)
            Item("Display", on_select=push(self._display_menu), submenu=True),
            Item("Connectivity", on_select=push(self._connectivity_menu), submenu=True),
            Item("System", on_select=push(self._system_menu), submenu=True),
        ])

    # ---- connectivity: Wi-Fi / Bluetooth radios + pairing (#299) ----
    def _connectivity_menu(self):
        return MenuScreen("Connectivity", [
            Item("Wi-Fi", on_select=(lambda: self._toggle_radio("wifi")),
                 value=(lambda: "off" if self._radio_blocked("wifi") else "on")),
            Item("Bluetooth", on_select=(lambda: self._toggle_radio("bluetooth")),
                 value=(lambda: "off" if self._radio_blocked("bluetooth") else "on")),
            Item("Bluetooth devices", on_select=self._open_bluetooth, submenu=True),
        ])

    def _radio_blocked(self, kind):
        """True if the given radio (kind='wifi'|'bluetooth') is soft-blocked (#299)."""
        try:
            r = subprocess.run(["rfkill", "list", kind], capture_output=True, text=True, timeout=3)
            return "Soft blocked: yes" in r.stdout
        except (OSError, subprocess.SubprocessError):
            return False

    def _toggle_radio(self, kind):
        action = "unblock" if self._radio_blocked(kind) else "block"
        try:
            r = subprocess.run(["rfkill", action, kind], capture_output=True, timeout=5)
            if r.returncode != 0:
                self.toast("failed — needs migration 013")
        except (OSError, subprocess.SubprocessError):
            self.toast("failed — needs migration 013")
        self._poll_status(force=True)                  # reflect the toggle on the Home indicators (#306)

    def _display_menu(self):
        return MenuScreen("Display", [
            Item("Screen sleep", on_adjust=self._cycle_sleep, value=self._sleep_label),
            Item("Tiles per page", on_adjust=self._cycle_page_tiles,
                 value=(lambda: str(MenuScreen.per_page_tiles))),
            Item("Calibrate touchscreen", on_select=self.calibrate, submenu=True),
        ])

    def _tools_menu(self):
        return MenuScreen("Tools", [
            Item("Metronome", on_select=(lambda: self.stack.append(self._metronome_menu())),
                 value=(lambda: "running" if self.metro.running else None), submenu=True),
        ])

    # ---- System: info + power + reset (#300) ----
    def _system_menu(self):
        return MenuScreen("System", [
            Item("Hardware", on_select=(lambda: self.stack.append(self._info_hardware())), submenu=True),
            Item("Software", on_select=(lambda: self.stack.append(self._info_software())), submenu=True),
            Item("Reboot", on_select=(lambda: self._confirm("Reboot", lambda: self._power("reboot"))),
                 submenu=True),
            Item("Power off", on_select=(lambda: self._confirm("Power off", lambda: self._power("poweroff"))),
                 submenu=True),
            Item("Reset config", on_select=(lambda: self._confirm("Reset config", self._reset)),
                 submenu=True),
        ])

    def _midi_label(self):
        """The chosen MIDI keyboard, or 'Auto' (all detected) (#326)."""
        return self.midi_keyboard or "Auto"

    def _open_midi(self):
        """Choose which MIDI keyboard plays the synth (#326). 'Auto' = autoconnect all
        (default); a specific device routes only it. Applied by start-piano.sh on the next
        synth (re)start — persisted as midi_keyboard."""
        items = [Item("Test keyboard", on_select=self._open_midi_test, submenu=True),  # #331
                 Item("Auto (all keyboards)", on_select=(lambda: self._choose_midi("")),
                      marker=(lambda: not self.midi_keyboard))]
        for name, label in list_midi_inputs():
            items.append(Item(label, on_select=(lambda n=name: self._choose_midi(n)),
                              marker=(lambda n=name: self.midi_keyboard == n)))
        self.stack.append(MenuScreen("MIDI keyboard", items))

    def _choose_midi(self, name):
        self.midi_keyboard = name
        self._update_settings(midi_keyboard=name)
        if audio_active():                            # synth up → offer to restart now (#330)
            self._prompt_audio_restart()             # reuse the Restart-audio dialog SDK
        else:
            self.toast("Saved — applies on next start")

    def _midi_test_port(self):
        """aseqdump source for the test: the chosen keyboard, else the first detected (#331)."""
        if self.midi_keyboard:
            return self.midi_keyboard
        devs = list_midi_inputs()
        return devs[0][0] if devs else ""

    def _open_midi_test(self):
        """Live mini-keyboard fed straight from the device via aseqdump — works even when
        the synth is down (tests the MIDI input path only, #331)."""
        port = self._midi_test_port()
        if not port:
            self.toast("no MIDI keyboard detected")
            return
        self.midimon.open(port)
        self.stack.append(MenuScreen("Test keyboard", [], keyboard=True))

    def _dialog(self, title, yes_label, on_yes, no_label="Cancel", on_no=None):
        """Mini yes/no dialog SDK (#311): a 2-item screen — confirm vs dismiss. Reused
        for destructive confirms (#297/#300) and the audio-restart prompt."""
        self.stack.append(MenuScreen(title, [
            Item(yes_label, on_select=on_yes),
            Item(no_label, on_select=on_no or self.nav_back),
        ]))

    def _confirm(self, label, fn):
        """Confirmation screen for a destructive action (#297/#300)."""
        self._dialog(label + "?", label + " now", fn)

    def _close_dialog(self):
        """Pop a dialog opened with _dialog and re-render."""
        if len(self.stack) > 1:
            self.stack.pop()
        self.render()

    # ---- toast SDK (#320): transient message, auto-dismiss on a timer + on next tap ----
    def toast(self, msg, secs=3.0):
        """Show a transient message that fades on its own after `secs` (and on the next
        tap) — replaces footers that lingered until you changed page. Plain text, no
        decoration (#320: david preferred 'juste le texte')."""
        self._toast_msg = msg
        self._toast_until = time.monotonic() + secs
        self.render()

    def _reset(self):
        """Delete the user's settings (back to defaults) and revert the live session (#300).
        Touch calibration is kept (reset it via Display → Calibrate)."""
        for p in (SETTINGS_PATH, _legacy_json_path()):
            try:
                os.remove(p)
            except OSError:
                pass
        MenuScreen.per_page_tiles = 6
        self.sleep_after = SLEEP_DEFAULT
        self.soundcard = ""
        self.cur_font_path, self.cur_bp, self.cur_preset_name = None, None, ""
        self.metro.stop()
        self.metro.bpm, self.metro.beats, self.metro.vol = 100, 4, 80
        self.metro.home_pulse = False
        self.bt_names = {}; self._bt_names_dirty = False
        self.bt_sink = ""
        self.nav_cfg = self._nav_cfg_from({})        # MIDI nav back to defaults (off) (#373)
        self._set_gain(GAIN_DEFAULT)
        self.stack = [self._home_menu()]
        self._nav_reconcile()                        # stop the nav monitor (reset → disabled)

    def _power(self, action):
        """Run `systemctl <reboot|poweroff>`. Needs the polkit grant from migration 012
        (the UI is a sessionless service); on failure, show why instead of silently dying."""
        try:
            r = subprocess.run(["systemctl", action], capture_output=True, timeout=10)
            if r.returncode != 0:
                self.toast("failed — needs migration 012")
        except subprocess.TimeoutExpired:
            pass                                    # system is going down
        except (OSError, subprocess.SubprocessError):
            self.toast("failed")

    @staticmethod
    def _info_rows(title, rows):
        # Each value is either a callable (refreshed every render → live field #642) or
        # a static string (snapshotted once at build time; cheap).
        return MenuScreen(title, [Item(k, value=(v if callable(v) else (lambda v=v: v)))
                                  for k, v in rows])

    def _info_hardware(self):
        # Live fields use callables so the row refreshes while the screen is shown (#642).
        return self._info_rows("Hardware", [
            ("Board", board_model()),
            ("Health", lambda: health()[1]), # aggregate verdict incl. services (#325)
            ("CPU temp", cpu_temp),
            ("CPU clock", cpu_clock),        # ⚠ when throttled — shows the under-voltage effect (#325)
            ("Power", power_status),         # under-voltage/throttle — weak PSU shows here (#316)
            ("RAM", mem_info),
            ("Disk", disk_info),
            ("Screen", f"{self.fb.w}x{self.fb.h}"),
        ])

    def _info_software(self):
        radios = lambda: ("Wi-Fi " + ("off" if self._radio_blocked("wifi") else "on")
                          + " · BT " + ("off" if self._radio_blocked("bluetooth") else "on"))
        return self._info_rows("Software", [
            ("pisynth", VERSION),
            ("OS", os_pretty()),
            ("Kernel", os.uname().release),
            ("Host", socket.gethostname()),
            ("IP", local_ip),                # DHCP lease can change while we're up (#642)
            ("Radios", radios),
            ("Uptime", uptime_str),
            ("Soundfonts", lambda: str(len(self.fonts))),
        ])

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
        """Settings → Tiles per page (#276): cycle per_page_tiles through the presets,
        persist it, and reset paging so the change is visible immediately."""
        opts = PAGE_TILES_OPTIONS
        cur = MenuScreen.per_page_tiles
        i = opts.index(cur) if cur in opts else opts.index(6)
        MenuScreen.per_page_tiles = opts[(i + delta) % len(opts)]
        self._update_settings(page_tiles=MenuScreen.per_page_tiles)
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
        # Clamp to [GAIN_MIN, GAIN_MAX] and quantize to GAIN_STEP (#372); round
        # to 2 dp so float fuzz never leaks into the `state` line or set_gain.
        self.gain = round(min(GAIN_MAX, max(GAIN_MIN, round(g / GAIN_STEP) * GAIN_STEP)), 2)
        self.fs.set_gain(self.gain)

    def _open_settings(self):
        self.stack.append(self._settings_menu())

    # ---- navigation (touch / D-pad / socket all go through these) ----
    def nav_move(self, delta):
        self.cur.move(delta)
        per = self.cur._per_page()                   # keep the page in sync with the cursor (#308)
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
        if self.cur.title == "Bluetooth":            # leaving BT → stop the worker + scan (#287/#298)
            self._bt_scan = False
            self.bt.close()
        if self.cur.keyboard:                        # leaving the MIDI test → stop aseqdump (#331)
            self.midimon.close()
        if len(self.stack) > 1:
            self.stack.pop()
        self._nav_reconcile()                        # match navmon to the new top screen (#373)
        self.render()

    def nav_page(self, delta=1):
        self.cur.page_flip(delta)
        self.render()

    # ---- Home status indicators (#306) ----
    def _poll_status(self, force=False):
        """Refresh the cached Home-bar status (Wi-Fi/BT radios, BT-connected, MIDI).
        Throttled to once every 3 s so the idle tick never shells out on every
        frame; render() only reads the cached flags. Synth state comes from
        self._online (refresh_fonts already tracks it)."""
        now = time.monotonic()
        if not force and now - self._st_t0 < 3.0:
            return
        self._st_t0 = now
        self._st_wifi = not self._radio_blocked("wifi")
        self._st_bt = not self._radio_blocked("bluetooth")
        self._st_bt_conn = self._st_bt and bt_any_connected()   # device connected? (#306)
        self._st_midi = midi_input_present()
        self._st_audio = audio_output_present(self.soundcard, self.bt_sink)   # sound card OK → audio icon (#327)
        if force or now - self._health_t0 >= 20.0:    # health smiley on its own slow throttle (#325)
            self._health_t0 = now                     # (vcgencmd + systemctl → don't run every 3 s)
            self._health = health()[0]

    def calibrate(self):
        w, h, ins = self.fb.w, self.fb.h, 0.15
        targets = [(w * ins, h * ins), (w * (1 - ins), h * ins),
                   (w * (1 - ins), h * (1 - ins)), (w * ins, h * (1 - ins))]
        raws = []
        for i, (tx, ty) in enumerate(targets):
            self.view._draw_target(tx, ty, i + 1, len(targets))
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
        self.view._draw_verify(done, dot)
        for ev in self.touch.dev.read_loop():
            if ev.type == ecodes.EV_ABS:
                if ev.code == ecodes.ABS_X:
                    rx = ev.value
                elif ev.code == ecodes.ABS_Y:
                    ry = ev.value
                if touching and rx is not None and ry is not None and self.touch.affine:
                    dot = self.touch.map(rx, ry)
                    self.view._draw_verify(done, dot)
            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                if ev.value == 1:
                    touching = True
                elif ev.value == 0:
                    touching = False
                    if dot and done[0] <= dot[0] <= done[2] and done[1] <= dot[1] <= done[3]:
                        return
                    self.view._draw_verify(done, dot)

    # ---- render → delegate to the view layer (#308 step 5) ----
    def render(self, band=None):
        """`band` = (r0, r1) to blit only those framebuffer rows (#668): the Home metronome
        pulse repaints just the top bar so the per-beat redraw is cheap on the slow SPI panel."""
        if len(self.stack) == 1:
            self._poll_status()                      # refresh Home indicators before snapshot
        active = self._toast_msg if (self._toast_msg and time.monotonic() < self._toast_until) else None
        kbd = None
        if self.cur.keyboard:                        # MIDI test screen → snapshot the monitor (#331)
            mm = self.midimon
            kbd = MidiState(frozenset(mm.active), mm.lo, mm.hi, mm.last, mm.count)
        self.view.render(self.cur, Status(
            depth=len(self.stack), wifi=self._st_wifi, bt=self._st_bt, bt_conn=self._st_bt_conn,
            midi=self._st_midi, synth=self._online, audio=self._st_audio, metro_running=self.metro.running,
            metro_beat=self.metro.beat, metro_beats=self.metro.beats,
            metro_flash=self.metro.flash, metro_home_pulse=self.metro.home_pulse, toast=active,
            health=self._health, kbd=kbd, loading=self._loading, load_anim=self._load_frame,
            load_phase=self._load_phase), band=band)

    # ---- hit-testing (controller side; geometry lives on the Renderer, #308) ----
    def _stepper_at(self, x, y):
        """(delta, global_index) if (x,y) is on a +/- stepper of the current list screen,
        else (0, -1). Used for hold-to-repeat (#314)."""
        if y < self.view.BAR_H or self.cur.tiles:
            return 0, -1
        pos = (y - self.view.BAR_H) // self.view.ROW_H
        sl = self.cur.page_slice()
        if not (0 <= pos < len(sl)):
            return 0, -1
        gi, it = sl[pos]
        if not it.on_adjust:
            return 0, -1
        minus, plus, _ = self.view._stepper_rects(self.view._row_y(pos))
        if minus[0] <= x <= minus[2] and minus[1] <= y <= minus[3]:
            return -1, gi
        if plus[0] <= x <= plus[2] and plus[1] <= y <= plus[3]:
            return 1, gi
        return 0, -1

    def _hold_repeat(self, now):
        """Auto-repeat a held +/- stepper (#314): after a short delay, fire the adjust
        repeatedly while the finger stays on the button. A quick tap = one step (handled
        on release); a hold = a ramp. Rate is naturally bounded by the SPI render time."""
        hp = None if self.asleep else self.touch.held_pos()
        d, gi = self._stepper_at(*hp) if hp is not None else (0, -1)
        if not d:
            self._hold_delta = 0
            return
        if self._hold_delta == 0:                    # finger just landed on a stepper
            self._hold_delta = d
            self._hold_next = now + 0.40             # initial delay before auto-repeat
        elif now >= self._hold_next:
            self.cur.idx = gi                        # adjust the held row's item
            self.nav_adjust(d)                       # applies + renders
            self._hold_fired = True
            self._hold_next = now + 0.12

    # ---- input ----
    def handle_tap(self, x, y):
        self._toast_msg = ""                      # any tap dismisses a toast (#320)
        if y < self.view.BAR_H:                   # bar: back (left) / page (right)
            back = self.view._back_rect(len(self.stack))
            page = self.view._page_rect(self.cur)
            if back and back[0] <= x <= back[2]:
                self.nav_back()
            elif len(self.stack) == 1 and x <= 56:    # Home cog → Settings (#289)
                self._open_settings()
                self.render()
            elif len(self.stack) == 1 and self.view._home_metro_hit(x):  # Home: tap metronome → toggle (#339)
                self._metro_toggle()
                self.render()
            elif page and page[0] <= x <= page[2]:
                self.nav_page(-1 if x < (page[0] + page[2]) / 2 else 1)
            return
        if self.cur.tiles:
            self._hit_tiles(x, y)
        else:
            self._hit_list(x, y)

    def _hit_list(self, x, y):
        m = self.cur
        pos = (y - self.view.BAR_H) // self.view.ROW_H
        slice_ = m.page_slice()
        if not (0 <= pos < len(slice_)):
            return
        gi, it = slice_[pos]
        m.idx = gi
        if it.on_adjust:                          # − / + stepper buttons
            minus, plus, _ = self.view._stepper_rects(self.view._row_y(pos))
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
        for (gi, _), rect in zip(slice_, self.view._tile_grid(len(slice_), rows=self.view._fixed_rows(self.cur))):
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
                    f"metro={self.metro.bpm}/{self.metro.beats}:{'run' if self.metro.running else 'off'} "
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
                "gain_up": lambda: self._set_gain(self.gain + GAIN_STEP),
                "gain_down": lambda: self._set_gain(self.gain - GAIN_STEP),
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
        metro_r, metro_w = os.pipe()                    # metronome thread pings here per beat (#287)
        os.set_blocking(metro_r, False)
        self.metro.set_wake(metro_w)
        sel.register(metro_r, selectors.EVENT_READ, "metro")
        midi_r, midi_w = os.pipe()                       # MIDI monitor pings here per note (#331)
        os.set_blocking(midi_r, False)
        self.midimon.set_wake(midi_w)
        sel.register(midi_r, selectors.EVENT_READ, "midimon")
        nav_r, nav_w = os.pipe()                          # nav monitor pings here per note (#373)
        os.set_blocking(nav_r, False)
        self.navmon.set_wake(nav_w)
        sel.register(nav_r, selectors.EVENT_READ, "navmon")
        self._nav_reconcile()                            # open the nav port now if enabled (#373)
        while True:
            now = time.monotonic()
            timeout = 2.0
            if self._hold_delta or self.touch.held_pos() is not None:  # hold-to-repeat tick (#314)
                timeout = 0.08
            if self._loading:                          # animate the load spinner (#375)
                timeout = min(timeout, 0.12)
            if self._toast_until:                      # wake right at toast expiry (#320)
                timeout = max(0.05, min(timeout, self._toast_until - now))
            events = sel.select(timeout=timeout)
            now = time.monotonic()
            if not events:                             # idle tick
                if self._loading:                      # async font load (#375): animate + poll, skip the
                    if self._load_result is not None:  # rest (no synth chatter while it loads)
                        self._finish_load()
                    else:
                        self._load_frame += 1
                        if not self.asleep:
                            self.render()
                    continue
                self._hold_repeat(now)                 # auto-repeat a held +/- stepper (#314)
                if self._toast_msg and now >= self._toast_until:   # toast expired (#320)
                    self._toast_msg = ""
                    if not self.asleep:
                        self.render()
                changed = self.refresh_fonts()         # also applies saved preset on connect
                st = (self._st_wifi, self._st_bt, self._st_bt_conn, self._st_midi)
                self._poll_status()                    # Home indicators: radios + BT-connected + MIDI (#306)
                if (self._st_wifi, self._st_bt, self._st_bt_conn, self._st_midi) != st:
                    changed = True
                if changed and not self.asleep:
                    self.render()
                if self._restart_pending:              # confirm/timeout an audio restart (#282/#327)
                    el = now - self._restart_pending
                    if el >= 3.0 and audio_active():    # service back active → overwrite the toast
                        self._restart_pending = 0.0
                        self.toast("Audio service restarted")
                    elif el > 30.0:                    # gave up waiting (USB card / BT sink absent)
                        self._restart_pending = 0.0
                        self.toast("Restart still running…", secs=4)
                if self.cur.title == "Bluetooth" and not self.asleep:
                    if self._bt_scan and now - self._bt_scan_t0 >= 300:
                        self._toggle_scan()            # auto-off scan after 5 min (#298/#301)
                    self._rebuild_bt()                 # reflect the worker's cache/result (#287/#298)
                    if self._bt_names_dirty:           # remember any newly-resolved names (#301)
                        self._save_bt_names()
                    self.render()
                if self.cur.title in ("Hardware", "Software") and not self.asleep:
                    self.render()                       # live CPU temp / clock / uptime / IP (#642)
                if (not self.asleep and self.sleep_after
                        and now - self.last_active >= self.sleep_after):
                    self.sleep_screen()
                continue
            for key, _ in events:
                if key.data == "touch":
                    taps = self.touch.read_taps()
                    if not taps:
                        continue                       # press (no release yet) → hold-repeat handles it
                    self.last_active = now
                    fired = self._hold_fired           # did a hold auto-repeat fire? (#314)
                    self._hold_fired = False
                    self._hold_delta = 0
                    if self.asleep:
                        self.wake_screen()             # first touch only wakes
                    elif fired:
                        pass                            # hold already adjusted → swallow the release tap
                    else:
                        for x, y in taps:
                            self.handle_tap(x, y)
                elif key.data == "metro":              # per-beat ping → redraw the beat dots (#287)
                    try:
                        os.read(metro_r, 256)
                    except OSError:
                        pass
                    if self.cur.title == "Metronome" and not self.asleep:
                        self.render()
                    elif (len(self.stack) == 1 and self.metro.home_pulse and self.metro.running
                          and not self.asleep):        # Home: pulse the metronome icon, top-bar blit only (#668)
                        self.render(band=(0, self.view.BAR_H))
                elif key.data == "midimon":            # per-note ping → light the test keyboard (#331)
                    try:
                        os.read(midi_r, 256)
                    except OSError:
                        pass
                    if self.cur.keyboard and not self.asleep:
                        self.render()
                elif key.data == "navmon":             # per-note ping → drive UI nav / learn (#373)
                    try:
                        os.read(nav_r, 256)
                    except OSError:
                        pass
                    self._nav_on_events()
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


def main():
    """Run the appliance UI, restarting App on any crash to stay alive."""
    while True:
        try:
            App().run()
        except Exception as e:                       # keep the appliance alive
            print(f"[pisynth-ui] error: {e}", file=sys.stderr, flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
