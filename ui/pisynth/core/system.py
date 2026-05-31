"""System introspection: board model, IP, temp/power/RAM/disk/OS/uptime (#289/#316)."""
import shutil
import socket
import subprocess


def cpu_temp():
    """CPU temperature like '58°C', or '?' (#316)."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return f"{int(f.read().strip()) / 1000:.0f}°C"
    except (OSError, ValueError):
        return "?"


def cpu_clock():
    """Current ARM clock like '1400 MHz', with ' ⚠' when actively throttled (#325).
    The 3B+ ondemand governor idles at 600 MHz, so a low value alone is normal — the ⚠
    flags real throttling (get_throttled bit), and the Power row shows the cause."""
    try:
        out = subprocess.run(["vcgencmd", "measure_clock", "arm"], capture_output=True,
                             text=True, timeout=3).stdout.strip()
        mhz = int(out.split("=")[1]) // 1_000_000
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return "?"
    try:
        t = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                           text=True, timeout=3).stdout
        warn = " ⚠" if int(t.split("=")[1], 16) & 0x4 else ""   # 0x4 = throttled right now
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        warn = ""
    return f"{mhz} MHz{warn}"


def _svc_active(name):
    """True if a systemd unit is active; True on error (don't false-alarm) (#325)."""
    try:
        return subprocess.run(["systemctl", "is-active", name], capture_output=True,
                              text=True, timeout=4).stdout.strip() == "active"
    except (OSError, subprocess.SubprocessError):
        return True


def health():
    """Overall health: ('good'|'warn'|'crit', reason) (#325). Worst severity wins; at
    equal severity the HARDWARE cause is reported before software. Reads thermal +
    `vcgencmd get_throttled` + `systemctl is-active piano.service`. The synth (piano) is
    the only service that gates health; midi-bridge (Keystation D-pad → preset cycling) is
    optional — the box plays fine without it, so it must NOT degrade health (#670)."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read().strip()) // 1000
    except (OSError, ValueError):
        temp = None
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                             text=True, timeout=3).stdout
        bits = int(out.split("=")[1], 16)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        bits = 0
    uv, thr = bool(bits & 0x1), bool(bits & 0x4)
    # critical — hardware before software at this level (#325)
    if temp is not None and temp >= 80:
        return "crit", f"{temp}°C hot"
    if uv and thr:
        return "crit", "low voltage"
    if not _svc_active("piano.service"):
        return "crit", "synth down"
    # warning — hardware before software
    if temp is not None and temp >= 70:
        return "warn", f"{temp}°C warm"
    if uv:
        return "warn", "low voltage"
    if thr:
        return "warn", "throttled"
    # midi-bridge being down does NOT degrade health: it's the optional Keystation D-pad
    # preset-cycler, not the sound path — the synth plays fine without it (#670).
    return "good", "OK"


def power_status():
    """Pi power/throttle health decoded from `vcgencmd get_throttled` (#316). Active
    issues (under-voltage / throttled / temp-limit) are shown verbatim — a weak PSU is
    a common cause of instability; otherwise 'OK', or 'OK (past …)' for cleared flags."""
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                             text=True, timeout=3).stdout.strip()
        bits = int(out.split("=")[1], 16)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return "?"
    # Concise (#316: the Power row is narrow) — one token, worst-first. Under-voltage is
    # the root cause to act on; throttling is usually its consequence.
    for b, n in ((0x1, "low voltage"), (0x8, "temp limit"), (0x4, "throttled")):
        if bits & b:
            return n
    for b, n in ((0x10000, "low voltage"), (0x80000, "temp limit"), (0x40000, "throttled")):
        if bits & b:
            return f"OK (past {n})"
    return "OK"


def mem_info():
    """RAM summary like '742 / 906 MB free' (available / total) (#316)."""
    try:
        d = {}
        with open("/proc/meminfo") as f:
            for ln in f:
                parts = ln.split()
                if parts:
                    d[parts[0].rstrip(":")] = int(parts[1])     # kB
        total = d["MemTotal"] // 1024
        avail = d.get("MemAvailable", d.get("MemFree", 0)) // 1024
        return f"{avail} / {total} MB free"
    except (OSError, KeyError, ValueError, IndexError):
        return "?"


def disk_info():
    """Root filesystem usage like '7.3 / 29 GB (27%)' (#316)."""
    try:
        u = shutil.disk_usage("/")
        g = 1024 ** 3
        return f"{u.used / g:.1f} / {u.total / g:.0f} GB ({u.used * 100 // u.total}%)"
    except OSError:
        return "?"


def os_pretty():
    """OS name from /etc/os-release PRETTY_NAME, e.g. 'Debian GNU/Linux 13 (trixie)' (#316)."""
    try:
        with open("/etc/os-release") as f:
            for ln in f:
                if ln.startswith("PRETTY_NAME="):
                    return ln.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "?"


def uptime_str():
    """Uptime like '2h 5m' or '40m' (#316)."""
    try:
        with open("/proc/uptime") as f:
            s = int(float(f.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return "?"
    h, m = s // 3600, (s % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def board_model():
    """Board name from the device tree, e.g. 'Raspberry Pi 3 Model B Plus' (#289)."""
    try:
        with open("/proc/device-tree/model", "rb") as f:
            return f.read().rstrip(b"\x00").decode("utf-8", "replace").strip() or "?"
    except OSError:
        return "?"


def local_ip():
    """Best-effort primary IPv4 (the address you'd SSH to), '?' if offline (#289).
    Opening a UDP socket and connect() picks the source IP without sending anything."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 53))                   # TEST-NET-1: routable lookup, no packet sent
        return s.getsockname()[0]
    except OSError:
        return "?"
    finally:
        s.close()
