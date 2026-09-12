"""Write-through for the read-only root (#681 phase B).

With the overlay on, every write lands in RAM and is dropped at reboot. The few things a
user changes FROM THE SCREEN (preferences, calibration, Bluetooth pairings) are pushed down
to the SD card by the root helper `pisynth-readonly persist` (sudoers grant, migration 021).
Requests are debounced: a burst of changes (holding a +/- stepper) costs one SD write.
No-op when the overlay is off — the normal write already hit the card.
"""
import subprocess
import threading

HELPER = "/usr/local/sbin/pisynth-readonly"
DEBOUNCE_S = 5.0

_lock = threading.Lock()
_pending = set()
_timer = None


def overlay_active():
    try:
        with open("/proc/cmdline") as f:
            return "overlayroot=tmpfs" in f.read().split()
    except OSError:
        return False


def _flush():
    global _timer
    with _lock:
        paths, _timer = sorted(_pending), None
        _pending.clear()
    if not paths:
        return
    try:
        r = subprocess.run(["sudo", "-n", HELPER, "persist", *paths],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"[pisynth-ui] persist failed ({r.returncode}): {r.stderr.strip()}", flush=True)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[pisynth-ui] persist failed: {e}", flush=True)


def flush_now():
    """Write pending requests immediately — call before a reboot / power off."""
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
            _timer = None
    _flush()


def request_persist(path):
    """Schedule `path` (a file, its deletion, or a whitelisted dir) to be written through to
    the SD card DEBOUNCE_S after the last request. Returns immediately."""
    global _timer
    if not overlay_active():
        return
    with _lock:
        _pending.add(path)
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(DEBOUNCE_S, _flush)
        _timer.daemon = True
        _timer.start()
