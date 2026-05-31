"""io — hardware / device-backend adapters (#308).

One module per device so each is swappable in isolation (David: la partie
hardware doit etre exemplaire dans l'abstraction, eventuellement supersedable).
Contracts live in interfaces.py; app.py imports the concrete classes from here.
"""
from .bluetooth import Bluetooth, any_connected as bt_any_connected
from .display import Backlight, Framebuffer
from .interfaces import (BacklightControl, Display, PointerInput, SynthBackend)
from .metronome import Metronome, ensure_test_tune
from .midimon import MidiMonitor
from .synth import Fluid
from .touch import Touch

__all__ = ["Backlight", "Bluetooth", "bt_any_connected", "Fluid", "Framebuffer",
           "Metronome", "MidiMonitor", "Touch",
           "ensure_test_tune", "BacklightControl", "Display", "PointerInput", "SynthBackend"]
