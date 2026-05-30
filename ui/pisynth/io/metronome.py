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


def _click_pcm(freq, ms=45, vol=80, sr=44100):
    """Raw 16-bit mono PCM (bytes) for one enveloped click at volume vol (0-100), used by
    the streaming metronome (#648). Same envelope/timbre as the click WAVs (_gen_click)."""
    n = int(sr * ms / 1000)
    amp = max(0.0, min(1.0, vol / 100.0)) * 0.9          # cap < 1.0 to avoid clipping
    buf = bytearray()
    for i in range(n):
        env = (1.0 - i / n) ** 2                          # fast decay → a 'tick'
        buf += struct.pack("<h", int(amp * env * 32767 * math.sin(2 * math.pi * freq * i / sr)))
    return bytes(buf)


class Metronome:
    """Background metronome (#287/#648). The rhythm is driven by a PERSISTENT player fed
    raw PCM (#648): instead of forking aplay every beat — whose fork+device-open latency
    was *variable* and made the tempo wobble — we open ONE player once and stream it a
    bar of PCM at a time (accent on beat 1 + silence padding for the exact beat length).
    Writing to the player's stdin BLOCKS when its ALSA buffer is full, so the sound card's
    own clock paces us → sample-accurate timing, no per-beat fork. The output (ALSA card
    or BT sink) is built by the injected `stream_cmd` (so this io module stays free of app
    config). A separate light thread drives the on-screen beat dots off a monotonic clock.

    Keeps running when you leave the screen ('son seulement'). `vol` (0-100) scales the
    click amplitude (#648). `play_fn` is still used for the one-shot test_click."""

    SR = 44100

    def __init__(self, hi, lo):
        self.bpm = 100
        self.beats = 4
        self.vol = 80                                # click volume 0-100 (#648)
        self.card = ""                               # ALSA card for the click; "" = system default (#287)
        self.bt_sink = ""                            # BT sink MAC for the click; "" = none (#287)
        self.play_fn = None                          # injected one-shot player play(wav) for test_click
        self.stream_cmd = None                       # injected () -> (argv, env|None) for the persistent player (#648)
        self.running = False
        self.beat = 0                                # current beat 1..beats, 0 when stopped
        self.err = ""                                # last player failure, "" = none (surfaced by the UI, #648)
        self._hi, self._lo = hi, lo                  # click WAVs (test_click via play_fn)
        self._accent = self._normal = b""            # current-volume click PCM, rebuilt on start / vol change
        self._stop = threading.Event()
        self._audio_t = None                         # PCM writer thread
        self._beat_t = None                          # visual beat-dot thread
        self._proc = None                            # the persistent player process
        self._wake = None                            # write-end of a pipe; ping the UI per beat

    def set_wake(self, fd):
        self._wake = fd

    def _build_clicks(self):
        """(Re)render the accent/normal click PCM at the current volume (#648)."""
        self._accent = _click_pcm(1800, vol=self.vol, sr=self.SR)
        self._normal = _click_pcm(1200, vol=self.vol, sr=self.SR)

    def set_volume(self, vol):
        self.vol = max(0, min(100, int(vol)))
        if self.running:
            self._build_clicks()                     # writer picks it up on the next bar

    def start(self):
        if self.running:
            return
        self.err = ""
        self._build_clicks()
        self._proc = self._spawn_player()
        if self._proc is None:                       # spawn itself failed (no player binary)
            self.err = "metronome: cannot open output"
            return
        # The player opens its device THEN reads stdin. A failed open (e.g. the card is held
        # exclusively by the synth via direct ALSA → "device busy") makes it exit within a
        # few ms. Poll briefly so the UI can toast it NOW — the writer thread finding out
        # after start() returns would be too late for the toggle's toast check (#648).
        for _ in range(12):                          # ~120 ms worst case, one-shot on Start
            if self._proc.poll() is not None:
                self.err = "metronome: output busy / unavailable"
                self._proc = None
                return
            time.sleep(0.01)
        self.running = True
        self._stop.clear()
        self._audio_t = threading.Thread(target=self._audio_loop, daemon=True)
        self._beat_t = threading.Thread(target=self._beat_loop, daemon=True)
        self._audio_t.start()
        self._beat_t.start()

    def stop(self):
        self.running = False
        self._stop.set()
        self.beat = 0
        p, self._proc = self._proc, None
        if p:
            try:
                if p.stdin:
                    p.stdin.close()                  # unblocks a writer parked on backpressure
            except OSError:
                pass
            try:
                p.terminate()
            except OSError:
                pass

    def _spawn_player(self):
        """Open the persistent raw-PCM player from the injected stream_cmd (#648). Falls
        back to a plain default-device aplay if nothing was injected (e.g. in tests)."""
        if self.stream_cmd:
            argv, env = self.stream_cmd()
        else:
            argv, env = (["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-c", "1",
                          "-r", str(self.SR), "-"], None)
        try:
            return subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, env=env, bufsize=0)
        except OSError:
            return None

    def _beat_pcm(self, accent):
        """One beat of PCM at the current bpm: its click then silence to the exact beat
        length (#648). Built per beat (not per bar) so a BPM/beats/volume change is heard
        within one beat instead of one whole bar."""
        beat_bytes = int(round(self.SR * 60.0 / max(1, min(300, self.bpm)))) * 2  # 16-bit → ×2
        click = (self._accent if accent else self._normal)[:beat_bytes]
        return click + b"\x00" * max(0, beat_bytes - len(click))

    def _audio_loop(self):
        """Keep the player fed one beat at a time. The write BLOCKS on the player's full
        ALSA buffer → the card clock paces us, sample-accurately (#648). A write error
        (device busy / player died mid-run) breaks out and is surfaced via self.err."""
        i = 0
        while not self._stop.is_set():
            accent = (i % max(1, min(8, self.beats))) == 0
            try:
                self._proc.stdin.write(self._beat_pcm(accent))
            except (OSError, ValueError, AttributeError):
                if not self._stop.is_set():
                    self.err = "metronome: output stopped"
                    self.running = False
                break
            i += 1

    def _beat_loop(self):
        """Drive the on-screen beat dots off a monotonic clock (#648). Independent of the
        audio stream (which is sample-accurate on its own); a fixed sub-buffer phase offset
        between dot and click is imperceptible."""
        n, nxt = 0, time.monotonic()
        while not self._stop.is_set():
            n = n % max(1, self.beats) + 1
            self.beat = n
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

    def test_click(self):
        """Play one accent click immediately on the configured card — lets the user
        confirm the chosen output device without starting the metronome (#287). One-shot,
        so the per-call fork is fine here (it's the per-BEAT fork that #648 removed)."""
        wav = self._hi
        if not wav:
            return
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
