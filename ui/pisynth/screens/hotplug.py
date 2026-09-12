"""Hot-plug recovery (#2410): bring sound and MIDI back after a USB device is replugged.

Mixin for app.App, driven from the 3 s status poll (`_hotplug_poll`).

- **Sound card back → restart the synth.** When the card fluidsynth plays on is unplugged,
  its ALSA audio thread exits for good (fluidsynth 2.4 `fluid_alsa.c`: a write error other
  than EAGAIN/EPIPE/ESTRPIPE/EBADFD ends the thread) while the process — and piano.service —
  stay "active", so systemd never restarts it: silence until someone does. We restart it
  when the card comes back.
- **Keyboard (re)plugged → re-wire.** fluidsynth's autoconnect grabs the new ports by itself,
  but the MIDI-nav monitor, midi-bridge's D-pad mute and a specifically chosen keyboard
  (`midi.autoconnect=0`) were all bound to the old ports.
"""
import subprocess
import time

from ..core.audio import audio_active, midi_hw_clients, midi_route_to_fluid, synth_card_candidates
from ..core.hotplug import PresenceWatch


class HotplugMixin:
    def _hotplug_init(self):
        self._hp_cards = PresenceWatch(settle=2, require_seen=True)     # replugged card only
        self._hp_midi = PresenceWatch(settle=2, require_seen=False)     # any keyboard after boot

    def _hotplug_poll(self):
        """Called from the status poll. Cheap: two /proc reads; subprocesses only on an event."""
        if self.bt_sink:                             # BT output has its own wait/fallback path
            self._hp_cards.update(())
        else:
            back = self._hp_cards.update(synth_card_candidates(self.soundcard))
            if back:
                self._hotplug_card_back(sorted(back))
        keys = self._hp_midi.update(midi_hw_clients())
        if keys:
            self._hotplug_keyboard_back(sorted(keys))

    def _hotplug_card_back(self, cards):
        if not audio_active():                       # not running: its own start loop finds the card
            return
        print(f"[pisynth-ui] hotplug: sound card back {cards} → restarting piano.service", flush=True)
        if self._restart_audio():                    # AudioMixin: systemctl restart --no-block
            self._restart_pending = time.monotonic()
            self.toast("Sound card back — restarting audio…", secs=30)

    def _hotplug_keyboard_back(self, names):
        print(f"[pisynth-ui] hotplug: MIDI keyboard {names} → re-wiring", flush=True)
        self._nav_on_keyboard_back()                 # NavMixin: re-subscribe + re-silence nav port
        if self.midi_keyboard and self.midi_keyboard in names:
            midi_route_to_fluid(self.midi_keyboard, connect=True)   # autoconnect is off for it
        try:                                         # midi-bridge re-disconnects the D-pad port itself
            if subprocess.run(["systemctl", "is-active", "--quiet", "midi-bridge.service"],
                              timeout=4).returncode == 0:
                subprocess.run(["systemctl", "restart", "--no-block", "midi-bridge.service"],
                               capture_output=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
