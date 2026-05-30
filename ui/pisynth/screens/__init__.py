"""screens — per-feature controller mixins (#308).

The App controller was a single large class; its cohesive feature blocks (menu builders
+ their handlers, grouped by subject) live here, one module per feature, as mixins that
`app.App` inherits. Method bodies are unchanged — they stay `self.`-based and resolve
cross-feature calls through the MRO — so this is a physical split, not a rewrite. App
keeps the core controller (init, nav, render delegation, the run loop, dispatch) and the
home/soundfont domain.
"""
from .audio import AudioMixin
from .bluetooth import BluetoothMixin
from .metronome import MetronomeMixin
from .nav import NavMixin

__all__ = ["AudioMixin", "BluetoothMixin", "MetronomeMixin", "NavMixin"]
