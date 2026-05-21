"""Device-backend contracts (#308) — the swap points to keep exemplary.

Each io/ adapter satisfies one of these structurally (typing.Protocol → no
inheritance needed). They document what the upper layers rely on, so an adapter
can be replaced (SPI->HDMI display, fluidsynth->another engine, ...) without
touching them. Pure documentation: importing this changes no behaviour.
"""
from typing import Protocol


class Display(Protocol):
    """A frame sink. `blit` pushes a full PIL image; `w`/`h` are the pixel size."""
    w: int
    h: int

    def blit(self, img) -> None: ...


class BacklightControl(Protocol):
    """Panel backlight power. `set(on)` returns True when applied."""

    def set(self, on: bool) -> bool: ...


class PointerInput(Protocol):
    """A touch/pointer source feeding the navigation loop."""

    def fileno(self) -> int: ...
    def read_taps(self) -> list: ...
    def set_affine(self, coeffs) -> None: ...
    def map(self, rx: int, ry: int): ...
    def wait_raw_tap(self): ...


class SynthBackend(Protocol):
    """The sound-engine control plane (preset / gain / listings)."""

    @property
    def online(self) -> bool: ...
    def connect(self) -> bool: ...
    def fonts(self) -> list: ...
    def presets(self, sfid: int) -> list: ...
    def select(self, sfid: int, bank: int, prog: int) -> None: ...
    def set_gain(self, gain: float) -> None: ...
