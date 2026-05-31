"""Metronome audio backend (#287/#655/#668): the click is rendered by fluidsynth from a
generated SMF on channel 9 and clocked by aplaymidi (no per-beat fork). Also hosts the
generated nav-beep / audio-test WAVs. Self-contained (reads PISYNTH_SOUNDS from the env).
"""
import math
import os
import struct
import subprocess
import threading
import time
import wave

from .clicktrack import click_midi_file


# Nav feedback beeps (#378): generated WAVs, soundfont-INDEPENDENT (the old fluidsynth
# note inherited the loaded soundfont). (freq Hz, ms, waveform).
_NAV_BEEPS = {
    "aigu":  (1760, 70, "sine"),
    "grave": (587, 90, "sine"),
    "blip":  (988, 55, "square"),
    "click": (2600, 22, "sine"),
}


def _gen_beep(path, kind, amp=0.5, sr=44100):
    """Write a short enveloped beep to a mono 16-bit WAV (#378)."""
    freq, ms, shape = _NAV_BEEPS.get(kind, _NAV_BEEPS["aigu"])
    n = int(sr * ms / 1000)
    frames = bytearray()
    for i in range(n):
        env = (1.0 - i / n) ** 2                     # fast decay → a 'beep', not a tone
        s = math.sin(2 * math.pi * freq * i / sr)
        if shape == "square":
            s = 1.0 if s >= 0 else -1.0
        frames += struct.pack("<h", int(max(-1.0, min(1.0, amp * env * s)) * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


def ensure_nav_beep(kind, vol):
    """Path to the nav beep WAV for (kind, vol 0-100), generated once and cached by name
    (#378). vol scales the amplitude; 0 = a silent WAV (muted). None on failure."""
    if kind not in _NAV_BEEPS:
        kind = "aigu"
    vol = max(0, min(100, int(vol)))
    d = os.path.expanduser(os.environ.get("PISYNTH_SOUNDS", "~/.config/pisynth/sounds"))
    try:
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"nav-{kind}-{vol}.wav")
        if not os.path.exists(p):
            _gen_beep(p, kind, amp=vol / 100.0 * 0.9)   # cap < 1.0 to avoid clipping
        return p
    except (OSError, wave.Error):
        return None


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
    """Background metronome (#287/#655/#668). The click is rendered by the MAIN piano
    fluidsynth from a generated SMF on channel 9 (percussion) and clocked by aplaymidi
    through its ALSA-seq port — so it comes out of the piano's speakers, the tempo is paced
    by the seq queue (no per-beat fork, no PCM stream). `fluid_setup`/`fluid_teardown`
    (injected by the app) load the click font + a drum kit on ch9 and return the seq port.

    A separate light thread drives the on-screen beat dots off a monotonic clock. Keeps
    running when you leave the screen ('son seulement'). `vol` (0-100) scales the click
    velocity, applied live by regenerating the SMF (#655)."""

    SR = 44100

    def __init__(self):
        self.bpm = 100
        self.beats = 4
        self.vol = 80                                # click volume 0-100 → SMF velocity (#655)
        self.home_pulse = False                      # pulse the Home metronome icon on each beat (#668)
        self.click_cmd = None                        # injected (midi_path, seq_port) -> aplaymidi argv (#655)
        self.fluid_setup = None                      # injected () -> main FLUID Synth seq port (str), "" on failure (#655)
        self.fluid_teardown = None                   # injected () -> None: silence the click channel on the main fluid (#655)
        self.running = False
        self.beat = 0                                # current beat 1..beats, 0 when stopped
        self.flash = False                           # True for a short window on each beat → blink the icon (#648)
        self.err = ""                                # last failure, "" = none (surfaced by the UI)
        self._stop = threading.Event()
        self._beat_t = None                          # visual beat thread
        self._proc = None                            # aplaymidi process
        self._fluid_t = None                         # aplaymidi relaunch watcher (#655)
        self._port = ""                              # ALSA-seq target for aplaymidi, resolved on start
        self._wake = None                            # write-end of a pipe; ping the UI per beat

    def set_wake(self, fd):
        self._wake = fd

    def set_volume(self, vol):
        self.vol = max(0, min(100, int(vol)))
        if self.running:
            self.reload()                            # regenerate the SMF at the new velocity

    def start(self):
        if self.running:
            return
        self.err = ""
        self._stop.clear()
        if not self._start_piano():                  # err set by the starter
            self._stop.set()
            return
        self.running = True
        self._beat_t = threading.Thread(target=self._beat_loop, daemon=True)
        self._beat_t.start()

    def _start_piano(self):
        """The click is played by the MAIN fluidsynth (same card as the piano), mixed in.
        fluid_setup loads the click font + a drum kit on ch9 and returns the FLUID Synth
        seq port; we then aplaymidi the click SMF to it — the ALSA-seq queue keeps the tempo
        steady (#655)."""
        if not (self.fluid_setup and self.click_cmd):
            self.err = "metronome: not wired"
            return False
        self._port = self.fluid_setup() or ""        # load click font + drum kit on ch9; → seq port
        if not self._port:
            self.err = "metronome: click soundfont unavailable"
            return False
        return self._launch_aplaymidi()

    def _launch_aplaymidi(self):
        self._proc = self._spawn_aplaymidi()
        if self._proc is None:
            self.err = "metronome: aplaymidi failed"
            self._teardown_audio()
            return False
        self._fluid_t = threading.Thread(target=self._fluid_watch, daemon=True)
        self._fluid_t.start()
        return True

    def _spawn_aplaymidi(self):
        d = os.path.expanduser(os.environ.get("PISYNTH_SOUNDS", "~/.config/pisynth/sounds"))
        try:
            os.makedirs(d, exist_ok=True)
            midi = click_midi_file(os.path.join(d, "metro-click.mid"), self.bpm, self.beats, vol=self.vol)
            return subprocess.Popen(self.click_cmd(midi, self._port), stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except (OSError, ValueError):
            return None

    def _fluid_watch(self):
        """Relaunch aplaymidi if its long file ends while still running (#655)."""
        while not self._stop.is_set():
            p = self._proc
            if p is None:
                break
            p.wait()
            if self._stop.is_set():
                break
            self._proc = self._spawn_aplaymidi()      # file ran out → loop the metronome
            if self._proc is None:
                self.err = "metronome: aplaymidi stopped"
                self.running = False
                break

    def reload(self):
        """Apply a live bpm/beats/vol change: regenerate the SMF + relaunch aplaymidi — kill
        the current run and the watcher respawns it from the new values (#655)."""
        if not self.running:
            return
        p = self._proc
        if p:
            try:
                p.terminate()                         # watcher's p.wait() returns → respawns fresh
            except OSError:
                pass

    def stop(self):
        self.running = False
        self._stop.set()
        self.beat = 0
        self.flash = False
        p, self._proc = self._proc, None
        if p:
            try:
                p.terminate()
            except OSError:
                pass
        self._teardown_audio()

    def _teardown_audio(self):
        """Release the click on stop/failure (#655): silence the click channel on the main
        (piano) fluidsynth — the light click font stays resident, spared by the loader."""
        if self.fluid_teardown:
            self.fluid_teardown()

    def _ping(self):
        if self._wake is not None:
            try:
                os.write(self._wake, b"x")            # wake the UI loop to redraw
            except OSError:
                pass

    def _beat_loop(self):
        """Drive the single blinking dot off a monotonic clock (#648): on each beat, flash
        ON (the UI lights the dot — yellow on beat 1, accent otherwise) then flash OFF part
        way through the beat → it blinks. Independent of the audio stream (sample-accurate
        on its own); a fixed sub-buffer phase offset between dot and click is imperceptible."""
        n, nxt = 0, time.monotonic()
        while not self._stop.is_set():
            d = nxt - time.monotonic()
            if d > 0 and self._stop.wait(d):          # wait to the beat boundary
                break
            if self._stop.is_set():
                break
            n = n % max(1, self.beats) + 1
            self.beat = n
            self.flash = True
            self._ping()                              # dot ON
            interval = 60.0 / max(1, min(300, self.bpm))
            nxt += interval
            if nxt < time.monotonic():                # fell behind → resync
                nxt = time.monotonic()
            if self._stop.wait(min(0.12, interval * 0.4)):   # ON window, then dim
                break
            self.flash = False
            self._ping()                              # dot OFF (blink)

