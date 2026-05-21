"""Metronome audio backend (#287): generates click WAVs and plays them via aplay
on a background thread. Self-contained (reads PISYNTH_SOUNDS from the env only).
"""
import math
import os
import struct
import subprocess
import threading
import time
import wave


def _gen_click(path, freq, ms=45, sr=44100):
    """Write a short enveloped sine click to a mono 16-bit WAV (metronome, #287)."""
    n = int(sr * ms / 1000)
    frames = bytearray()
    for i in range(n):
        env = (1.0 - i / n) ** 2                     # fast decay → a 'tick'
        frames += struct.pack("<h", int(0.6 * env * 32767 * math.sin(2 * math.pi * freq * i / sr)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


def ensure_clicks():
    """Generate the metronome click WAVs once (no binary assets in the repo) and return
    (accent, normal) paths, or (None, None) if generation fails (#287)."""
    d = os.path.expanduser(os.environ.get("PISYNTH_SOUNDS", "~/.config/pisynth/sounds"))
    try:
        os.makedirs(d, exist_ok=True)
        hi, lo = os.path.join(d, "click-hi.wav"), os.path.join(d, "click-lo.wav")
        if not os.path.exists(hi):
            _gen_click(hi, 1800)
        if not os.path.exists(lo):
            _gen_click(lo, 1200)
        return hi, lo
    except (OSError, wave.Error):
        return None, None


# A short ORIGINAL fanfare for the audio Test (#318) — generated, not a copyrighted
# theme. (freq Hz, ms); 0 = rest. ~3 s, recognisable as "music came out".
_TEST_TUNE = [(196.0, 200), (261.63, 200), (329.63, 200), (392.0, 200), (523.25, 420),
              (0, 90), (329.63, 160), (392.0, 160), (523.25, 160), (659.25, 160),
              (783.99, 760)]


def _gen_tune(path, notes, sr=44100):
    """Write a sequence of enveloped sine notes to a mono 16-bit WAV (#318). Each note
    gets a quick attack + gentle decay so it sounds musical rather than a beep."""
    frames = bytearray()
    atk = int(0.008 * sr)
    for freq, ms in notes:
        n = int(sr * ms / 1000)
        for i in range(n):
            if freq <= 0:
                frames += struct.pack("<h", 0)
                continue
            env = min(1.0, i / atk) * ((1.0 - i / n) ** 0.4)
            frames += struct.pack("<h", int(0.5 * env * 32767 * math.sin(2 * math.pi * freq * i / sr)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


def ensure_test_tune():
    """Generate the audio-test tune WAV once and return (path, duration_ms), or
    (None, 0) on failure (#318)."""
    d = os.path.expanduser(os.environ.get("PISYNTH_SOUNDS", "~/.config/pisynth/sounds"))
    ms = sum(n[1] for n in _TEST_TUNE)
    try:
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "test-tune.wav")
        if not os.path.exists(path):
            _gen_tune(path, _TEST_TUNE)
        return path, ms
    except (OSError, wave.Error):
        return None, 0


class Metronome:
    """Background metronome (#287): a thread ticks at the BPM and plays a click WAV via
    aplay on each beat (accent on beat 1). Keeps running when you leave the screen
    ('son seulement' in the background). The click can be routed to a chosen ALSA card
    (`card`) so it uses a different output than the synth ('carte son differente').
    Still open: click-sound choice, dedicated-fluidsynth backend, Bluetooth-sink output."""

    def __init__(self, hi, lo):
        self.bpm = 100
        self.beats = 4
        self.card = ""                               # ALSA card for the click; "" = system default (#287)
        self.bt_sink = ""                            # BT sink MAC for the click; "" = none (#287)
        self.play_fn = None                          # injected player play(wav); falls back to aplay
        self.running = False
        self.beat = 0                                # current beat 1..beats, 0 when stopped
        self._hi, self._lo = hi, lo
        self._stop = threading.Event()
        self._thread = None
        self._wake = None                            # write-end of a pipe; ping the UI per beat

    def set_wake(self, fd):
        self._wake = fd

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop.set()
        self.beat = 0

    def _loop(self):
        n, nxt = 0, time.monotonic()
        while not self._stop.is_set():
            n = n % max(1, self.beats) + 1
            self.beat = n
            self._click(n == 1)
            if self._wake is not None:
                try:
                    os.write(self._wake, b"x")        # wake the UI loop to redraw the beat
                except OSError:
                    pass
            nxt += 60.0 / max(1, min(300, self.bpm))
            d = nxt - time.monotonic()
            if d < 0:                                 # fell behind → resync
                nxt, d = time.monotonic(), 0
            self._stop.wait(d)

    def _click(self, accent):
        wav = self._hi if accent else self._lo
        if not wav:
            return
        # The output (ALSA card OR BT sink) can differ from the synth's ('carte son
        # differente', #287) — fluidsynth holds the USB card via direct ALSA, so the
        # metronome usually wants the onboard jack/HDMI/BT instead. The controller
        # injects play_fn to route ALSA (aplay) vs BT (pw-play) (#287); we fall back to
        # plain aplay if it isn't set.
        if self.play_fn:
            self.play_fn(wav)
            return
        cmd = ["aplay", "-q"]
        if self.card:
            cmd += ["-D", f"plughw:{self.card}"]
        cmd.append(wav)
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def test_click(self):
        """Play one accent click immediately on the configured card — lets the user
        confirm the chosen output device without starting the metronome (#287)."""
        self._click(True)
