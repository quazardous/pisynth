"""Audio screens (#282/#301/#311/#314/#318), split out of the controller (#308).

Mixin for app.App: gain/volume steppers, the output device picker (ALSA cards + BT A2DP
sinks), the test sound, and the restart-now prompt. Cross-feature helpers (toast,
_dialog/_close_dialog, _confirm, _update_settings, _set_gain) resolve via the MRO.
"""
import subprocess
import time

from ..core.audio import (alsa_volume, bt_volume, list_audio_cards, play_test,
                          set_alsa_volume, set_bt_volume)
from ..core.settings import load_settings
from ..io import ensure_test_tune
from ..ui.menu import Item, MenuScreen
from .devices import output_label, output_picker_items


class AudioMixin:
    def _audio_menu(self):
        self.volume = self._read_volume()            # refresh cached output volume on open (#314)
        return MenuScreen("Audio", [
            Item("Gain", on_adjust=(lambda d: self._set_gain(self.gain + 0.5 * d)),
                 value=(lambda: f"{self.gain:.1f}"), bar=(lambda: self.gain / 10.0)),
            Item("Volume", on_adjust=self._set_volume, value=self._volume_label,
                 bar=(lambda: (self.volume or 0) / 100.0)),
            Item("Audio device", on_select=self._open_audio,
                 value=self._audio_label, submenu=True),
            Item("Test sound", on_select=self._test_audio),    # #318
        ])

    def _test_audio(self):
        """Play a short tune on the active output to confirm it works (#318) — independent
        of the synth, so it isolates 'is the device making sound?'. The toast auto-clears
        when the tune ends (#320)."""
        path, ms = ensure_test_tune()
        if play_test(path, self.soundcard, self.bt_sink):
            self.toast("playing test sound…", secs=ms / 1000.0 + 0.5)
        else:
            self.toast("no output to test")

    # ---- output volume (#314): hardware/mixer level, distinct from synth.gain ----
    def _active_card(self):
        """ALSA card whose mixer the Volume stepper drives: the chosen card, else (Auto)
        the first present non-HDMI playback card. Only consulted for the ALSA path."""
        if self.soundcard:
            return self.soundcard
        cards = list_audio_cards()
        return cards[0][0] if cards else None

    def _read_volume(self):
        if self.bt_sink:                             # BT A2DP sink → wpctl (#314)
            return bt_volume(self.bt_sink)
        card = self._active_card()                   # ALSA card → amixer
        return alsa_volume(card) if card else None

    def _volume_label(self):
        return f"{self.volume}%" if self.volume is not None else "—"

    def _set_volume(self, delta):
        if self.volume is None:
            return                                   # no controllable output (fixed-level / absent)
        nv = max(0, min(100, self.volume + delta))   # 1%/step — hold +/- to ramp (#314)
        if self.bt_sink:
            ok = set_bt_volume(self.bt_sink, nv)
        else:
            card = self._active_card()
            ok = set_alsa_volume(card, nv) if card else False
        if ok:
            self.volume = nv                         # only commit the displayed value if it took

    # ---- audio device picker (ticket #282; Bluetooth A2DP output #301) ----
    def _audio_label(self):
        """Friendly name of the active output (BT sink / ALSA card / 'Auto'), from the
        cheap persisted name cache — never spawns pw-dump here (renders every frame)."""
        return output_label(self.soundcard, self.bt_sink, self.bt_names, "Auto")

    def _open_audio(self):
        # One picker, two output families: ALSA cards (direct, low-latency) and connected
        # BT A2DP sinks (#301). Choosing one clears the other (the _choose_* handlers).
        self.stack.append(MenuScreen("Audio device", output_picker_items(
            "Auto (detect USB)", lambda: self.soundcard, lambda: self.bt_sink,
            lambda: self._choose_soundcard(""), self._choose_soundcard, self._choose_bt_sink)))

    def _choose_soundcard(self, name):
        self.soundcard = name
        self.bt_sink = ""                          # selecting an ALSA card drops any BT output (#301)
        self._update_settings(soundcard=name)
        self._update_bt_pref(audio_sink="")
        self._prompt_audio_restart()

    def _choose_bt_sink(self, mac, label=""):
        """Route the synth to a Bluetooth A2DP sink (#301). Persisted as
        bluetooth.audio_sink (MAC); start-piano.sh then runs fluidsynth on the
        pulseaudio driver instead of grabbing an ALSA card. The sink's name is cached
        (bluetooth.known) so _audio_label can show it without re-querying PipeWire."""
        self.bt_sink = mac
        self.soundcard = ""
        self._remember_bt_name(mac, label)
        self._update_bt_pref(audio_sink=mac)
        self._update_settings(soundcard="")
        self._prompt_audio_restart()

    def _prompt_audio_restart(self):
        """Audio output changed → ask whether to restart the synth now (#311)."""
        self._dialog("Restart audio now?", "Restart", self._apply_audio_restart,
                     "Not now", on_no=self._dismiss_audio_restart)

    def _apply_audio_restart(self):
        applied = self._restart_audio()
        self._close_dialog()
        if applied:
            self._restart_pending = time.monotonic()   # idle tick toasts when it's back (#282)
            self.toast("Restarting audio…", secs=30)
        else:
            self.toast("Saved — applies on next restart")

    def _dismiss_audio_restart(self):
        self._close_dialog()
        self.toast("Saved — applies on next restart")

    def _update_bt_pref(self, **kw):
        """Merge keys into the settings.yaml `bluetooth` map without clobbering the
        rest of it (e.g. the `known` name cache) (#301)."""
        bt = dict((load_settings().get("bluetooth") or {}))
        bt.update(kw)
        self._update_settings(bluetooth=bt)

    def _restart_and_note(self):
        applied = self._restart_audio()
        self.toast("Restarting audio…" if applied else "Saved — applies on next restart")

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
