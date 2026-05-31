"""MIDI navigation (#373): drive the pisynth UI from a MIDI keyboard.

David's ask: pilot the menus with keys (à la nanosynth's D-pad), with a screen to
*define* which key does what, an optional beep feedback, and the whole thing opt-in.

Design
------
- A second `MidiMonitor` (`self.navmon`, distinct from the #331 test-keyboard one)
  runs `aseqdump` on the chosen MIDI port. Each note-on is queued (`navmon.drain`)
  and mapped, via `nav_cfg["bindings"]`, to the existing screen-agnostic nav API
  (`nav_move / nav_select / nav_back / nav_page`) — the same calls touch and the
  :9810 socket already use, so navigation works on every screen for free.
- The port is configurable (David: « ça dépend du hardware »). Default = the 2nd
  port if present, else the last — never `:0`, which is normally the main keyboard
  (and would *sound* when pressed). A control port like the Keystation's `:1` is
  already disconnected from fluidsynth by midi-bridge.sh → silent.
- Off by default. Optional beep feedback (off by default) is a short GM-percussion note on
  the synth's reserved channel 9 — the SAME path as the metronome click (#673): the ch9 drum
  kit is fixed (TimGM6mb), so the beep is soundfont-INDEPENDENT, and it plays through the
  synth's own card (no `aplay` → no contention with the exclusive ALSA-direct output, which
  silenced the old generated-WAV beep, #378/#673).

Cross-feature helpers (toast, _update_settings, nav_*, fs, render) resolve via the MRO.
"""
import subprocess
import time

from ..core.audio import list_midi_ports, midi_route_to_fluid
from ..io import MidiMonitor
from ..ui.menu import Item, MenuScreen

# Nav actions named after the D-pad directions (david). All four directions MOVE the
# cursor (←→ by one cell, ↑↓ by a row on a tile grid); ↑↓ auto-flip the page at the
# edge so no separate "Page" key is needed. Sélection = tap (enter/choose). Retour is an
# OPTIONAL extra (david: « pas essentiel ») — unbound by default since the 5-button D-pad
# is fully used; map it to any key via learn-by-press if wanted.
NAV_ACTIONS = [("up", "Up"), ("down", "Down"), ("left", "Left"),
               ("right", "Right"), ("select", "Select"), ("back", "Back")]
# Defaults = the Keystation D-pad notes (nanosynth: ↑96 ↓97 ←98 →99 ●100); Retour unbound.
NAV_DEFAULT_BINDINGS = {"up": 96, "down": 97, "left": 98, "right": 99,
                        "select": 100, "back": None}
# Selectable beep sounds (#378) → mapped to GM percussion notes on channel 9 (#673),
# soundfont-independent (the ch9 drum kit is fixed). key → label.
NAV_BEEPS = [("aigu", "High"), ("grave", "Low"), ("blip", "Blip"), ("click", "Click")]
NAV_DEFAULT_BEEP = "aigu"
NAV_DEFAULT_VOL = 40        # beep loudness 0-100% → MIDI velocity (#373/#673)
# GM percussion notes (bank 128) for each beep kind: high/low woodblock, cowbell, side stick.
NAV_BEEP_NOTES = {"aigu": 76, "grave": 77, "blip": 56, "click": 37}


class NavMixin:
    # ---- config lifecycle ----
    def _nav_cfg_from(self, nav):
        """Build the in-memory nav config from a persisted (possibly partial) dict,
        merging defaults so a settings.yaml missing keys still yields a full config."""
        binds = {**NAV_DEFAULT_BINDINGS}
        for k, v in (nav.get("bindings") or {}).items():
            if k in NAV_DEFAULT_BINDINGS and v is not None:
                binds[k] = int(v)
        beep = str(nav.get("beep", NAV_DEFAULT_BEEP))
        if beep not in dict(NAV_BEEPS):                 # migrate old GM-program ints → default (#378)
            beep = NAV_DEFAULT_BEEP
        return {
            "enabled": bool(nav.get("enabled", False)),
            "port": nav.get("port", "") or "",          # "" = auto (2nd/last)
            "bindings": binds,
            "sound": bool(nav.get("sound", False)),
            "beep": beep,                               # generated-WAV kind (#378)
            "beep_vol": max(0, min(100, int(nav.get("beep_vol", NAV_DEFAULT_VOL)))),  # 0-100% (#373)
        }

    def _nav_init(self, s):
        """Called once from App.__init__ with the loaded settings dict."""
        self.nav_cfg = self._nav_cfg_from(s.get("nav") or {})
        self.navmon = MidiMonitor()      # dedicated monitor (separate from the test keyboard)
        self._navmon_port = ""           # port aseqdump is currently bound to ("" = closed)
        self._nav_learn = None           # action awaiting a learn-by-press capture, or None

    def _nav_save(self):
        self._update_settings(nav=self.nav_cfg)

    def _nav_resolve_port(self):
        """The port to listen on: the explicit choice, else auto = 2nd port if it
        exists, else the last (never the first = main keyboard). "" if none found."""
        if self.nav_cfg["port"]:
            return self.nav_cfg["port"]
        ports = list_midi_ports()
        if not ports:
            return ""
        return ports[1][0] if len(ports) > 1 else ports[-1][0]

    def _nav_listening_wanted(self):
        """Listen when nav is enabled OR while the user is on the Navigation screen
        (so the live learn-by-press works even before the feature is switched on)."""
        return self.nav_cfg["enabled"] or any(m.title == "Navigation" for m in self.stack)

    def _nav_reconcile(self):
        """Make the nav input match the wanted state + current port — in one place, on
        every transition (toggle / port change / screen enter-leave). When a nav port is
        live we (1) read it with navmon, (2) disconnect it from fluidsynth so its raw
        notes don't play, and (3) stop midi-bridge.service so the D-pad's R2D2 beep +
        preset-cycle don't double-fire (david). All three are reversed when nav lets go.
        Idempotent: a no-op when the resolved port is already the active one."""
        port = self._nav_resolve_port() if self._nav_listening_wanted() else ""
        if port == self._navmon_port:
            return                                       # no transition
        if self._navmon_port:                            # tearing down the old port
            midi_route_to_fluid(self._navmon_port, connect=True)   # restore its sound
        if port:                                         # bringing up the new port
            self.navmon.open(port)
            midi_route_to_fluid(port, connect=False)     # silence the nav port
        else:
            self.navmon.close()
        self._navmon_port = port
        self._nav_set_bridge(active=bool(port))          # pause/restore the D-pad bridge

    def _nav_on_synth_online(self):
        """Re-disconnect the nav port from the synth when it (re)connects (#373). At boot
        the UI runs _nav_reconcile before fluidsynth is up, so the one-shot disconnect is a
        no-op and `midi.autoconnect=1` then wires the port to the synth → its raw notes
        play. Re-asserting on the offline→online edge wins that race."""
        if self._navmon_port:
            midi_route_to_fluid(self._navmon_port, connect=False)

    def _nav_set_bridge(self, active):
        """Stop midi-bridge.service while nav owns the D-pad, start it again otherwise.
        Without this the bridge's loud beep + preset cycling fire on every nav press
        (david: « le son est très fort »). Uses the polkit grant from migration 016;
        non-blocking so the UI never stalls on the bridge's slow startup."""
        action = "stop" if active else "start"
        try:
            subprocess.run(["systemctl", action, "--no-block", "midi-bridge.service"],
                           capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass

    # ---- the per-wake event handler (called from the run loop on a navmon ping) ----
    def _nav_on_events(self):
        notes = self.navmon.drain()
        if not notes:
            return
        if self._nav_learn:                              # learn-by-press: capture, don't navigate
            self.nav_cfg["bindings"][self._nav_learn] = notes[-1]
            self._nav_learn = None
            self._nav_save()
            self.toast(f"key {notes[-1]} bound")
            self.render()
            return
        if not self.nav_cfg["enabled"]:
            return
        if self.asleep:                                  # first press only wakes (like a touch)
            self.wake_screen()
            return
        self.last_active = time.monotonic()
        rev = {n: a for a, n in self.nav_cfg["bindings"].items() if n is not None}
        for n in notes:
            action = rev.get(n)
            if action:
                self._nav_beep(action)
                self._nav_dispatch(action)

    def _nav_dispatch(self, action):
        # 2D grid navigation (david). Tile grid is 3-wide (renderer._tile_grid cols=3).
        # Haut/Bas: keep the column, move between rows, wrapping vertically (skip a partial
        # row lacking that column). Gauche/Droite: move within the row; at the screen edge,
        # if there are several pages, FLIP the page keeping the same row-in-page (#376), else
        # wrap within the row (#373). Plain lists (cols=1) just step ±1.
        if action == "select":
            self.nav_select()                            # = tap (enter / choose)
            return
        if action == "back":
            self.nav_back()                              # optional, non-essential
            return
        n = len(self.cur.items)
        if n <= 1:
            return
        cols = 3 if getattr(self.cur, "tiles", False) else 1
        idx = self.cur.idx
        if cols <= 1:                                    # list: up/left = prev, down/right = next
            self.nav_move(-1 if action in ("up", "left") else 1)
            return
        col = idx % cols
        if action in ("up", "down"):                    # vertical: keep column, wrap (#373)
            d = 1 if action == "down" else -1
            nrows = (n + cols - 1) // cols
            target, r = idx, idx // cols
            for _ in range(nrows):
                r = (r + d) % nrows
                cand = r * cols + col
                if cand < n:                             # skip rows that lack this column
                    target = cand
                    break
            self.nav_move(target - idx)
            return
        # horizontal: within the row; at the screen edge flip the page (#376) keeping the
        # row-in-page, else (single page) wrap within the row (#373).
        d = 1 if action == "right" else -1
        per = self.cur._per_page()
        page = idx // per
        r = (idx % per) // cols                          # row within the visible page
        row_base = page * per + r * cols
        row_len = min(cols, n - row_base, (page + 1) * per - row_base)
        nc = col + d
        if 0 <= nc < row_len:                            # stay in the row
            target = row_base + nc
        elif self.cur.npages() > 1:                      # screen edge + pagination → flip page (#376)
            np = self.cur.npages()
            nb = ((page + d) % np) * per + r * cols
            nlen = min(cols, max(0, n - nb), max(0, ((page + d) % np + 1) * per - nb))
            if nlen <= 0:                                # that row is absent on a partial page
                target = ((page + d) % np) * per
            else:
                target = nb if d == 1 else nb + nlen - 1
        else:                                            # single page → wrap within the row (#373)
            target = row_base + nc % row_len
        self.nav_move(max(0, min(target, n - 1)) - idx)

    def _nav_beep(self, action=None):
        """Play the chosen feedback beep, if sound is on (#373/#673): a short GM-percussion
        note on the synth's reserved channel 9 (same path as the metronome click) — fixed
        drum kit so it's soundfont-independent, played through the synth's card (no aplay →
        no contention). Fire-and-forget; silent when the synth is offline or volume is 0."""
        if not self.nav_cfg["sound"] or getattr(self, "_loading", False):  # quiet during a load (#375)
            return
        vol = self.nav_cfg["beep_vol"]
        if vol <= 0 or not self.fs.online:           # muted, or no synth to play it
            return
        note = NAV_BEEP_NOTES.get(self.nav_cfg["beep"], NAV_BEEP_NOTES[NAV_DEFAULT_BEEP])
        vel = max(1, min(127, round(vol / 100 * 127)))
        try:
            self.fs.send(f"noteon 9 {note} {vel}")   # ch9 = the fixed drum kit (#655/#673)
        except OSError:
            pass

    # ---- the Navigation settings screen ----
    def _open_nav(self):
        self.stack.append(self._nav_menu())
        self._nav_reconcile()                            # start listening for live learn

    def _nav_menu(self):
        items = [
            Item("Enable", on_select=self._nav_toggle_enabled,
                 value=(lambda: "on" if self.nav_cfg["enabled"] else "off")),
            Item("Port", on_select=self._nav_open_port,
                 value=(lambda: self._nav_resolve_port() or "—"), submenu=True),
        ]
        for key, label in NAV_ACTIONS:
            items.append(Item(label, on_select=(lambda k=key: self._nav_learn_start(k)),
                              value=(lambda k=key: self._nav_key_label(k))))
        items += [
            Item("Sound", on_select=self._nav_toggle_sound,
                 value=(lambda: "on" if self.nav_cfg["sound"] else "off")),
            Item("Beep", on_select=self._nav_open_beep, value=self._nav_beep_label, submenu=True),
            Item("Volume", on_adjust=self._nav_vol_adjust,
                 value=(lambda: f"{self.nav_cfg['beep_vol']}%"),
                 bar=(lambda: self.nav_cfg["beep_vol"] / 100.0)),
        ]
        return MenuScreen("Navigation", items)

    def _nav_key_label(self, key):
        n = self.nav_cfg["bindings"].get(key)
        return str(n) if n is not None else "—"

    def _nav_beep_label(self):
        return dict(NAV_BEEPS).get(self.nav_cfg["beep"], str(self.nav_cfg["beep"]))

    def _nav_toggle_enabled(self):
        self.nav_cfg["enabled"] = not self.nav_cfg["enabled"]
        self._nav_save()
        self._nav_reconcile()

    def _nav_toggle_sound(self):
        self.nav_cfg["sound"] = not self.nav_cfg["sound"]
        self._nav_save()

    def _nav_vol_adjust(self, delta):
        self.nav_cfg["beep_vol"] = max(0, min(100, self.nav_cfg["beep_vol"] + 10 * delta))
        self._nav_save()
        self._nav_beep("select")                         # audition the new level

    def _nav_learn_start(self, key):
        """Enter learn mode for one action: the next note-on on the nav port is
        captured as its binding (handled in _nav_on_events)."""
        self._nav_learn = key
        self._nav_reconcile()                            # ensure navmon is up to capture
        label = dict(NAV_ACTIONS).get(key, key)
        self.toast(f'press a key for "{label}"…', secs=10)

    def _nav_open_port(self):
        items = [Item("Auto (2nd/last)", on_select=(lambda: self._nav_set_port("")),
                      marker=(lambda: not self.nav_cfg["port"]))]
        for spec, label in list_midi_ports():
            sounds = spec.endswith(":0")                 # :0 is usually the main keyboard → it sounds
            items.append(Item(label + (" ⚠" if sounds else ""),
                              on_select=(lambda s=spec: self._nav_set_port(s)),
                              marker=(lambda s=spec: self.nav_cfg["port"] == s)))
        self.stack.append(MenuScreen("Port", items))

    def _nav_set_port(self, spec):
        self.nav_cfg["port"] = spec
        self._nav_save()
        self._nav_reconcile()                            # restores old port + silences new one

    def _nav_open_beep(self):
        items = []
        for prog, name in NAV_BEEPS:
            items.append(Item(name, on_select=(lambda p=prog: self._nav_set_beep(p)),
                              marker=(lambda p=prog: self.nav_cfg["beep"] == p)))
        self.stack.append(MenuScreen("Beep", items))

    def _nav_set_beep(self, prog):
        self.nav_cfg["beep"] = prog
        self._nav_save()
        self._nav_beep("select")                         # audition the chosen voice
