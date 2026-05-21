"""Audio output enumeration: ALSA playback cards, USB-MIDI presence, BT sinks (#282/#301/#306)."""
import glob
import json
import os
import re
import subprocess

def list_audio_cards():
    """[(name, label), ...] of ALSA cards that expose PCM playback (#282).
    `name` is the bracketed card id used as plughw:NAME — same token start-piano.sh
    persists/reads; `label` is a friendlier model name for the menu. MIDI-only
    devices (the Keystation) have no playback PCM and are skipped. HDMI (vc4hdmi)
    is skipped too: on this headless appliance it has no audio consumer, so the
    synth busy-loops at RT priority and freezes the UI (#311)."""
    cards = []
    try:
        text = open("/proc/asound/cards").read()
    except OSError:
        return cards
    for m in re.finditer(r"^\s*(\d+)\s+\[([^\]]+)\]\s*:\s*(.*)$", text, re.M):
        idx, name, desc = m.group(1), m.group(2).strip(), m.group(3).strip()
        if not glob.glob(f"/proc/asound/card{idx}/pcm*p"):
            continue                               # no playback PCM (e.g. USB-MIDI)
        if "hdmi" in (name + desc).lower():
            continue                               # HDMI = no consumer headless → runaway (#311)
        label = desc.split(" - ", 1)[-1].strip() or name   # "USB-Audio - M-Track Hub" -> "M-Track Hub"
        cards.append((name, label))
    return cards


def alsa_mixer_control(card):
    """Name of an ALSA card's main playback volume control (#314): 'PCM' on the Pi's
    bcm2835 jack, 'Master'/'Speaker'/… on others. '' if the card has no volume control
    (some USB DACs are fixed-level)."""
    try:
        out = subprocess.run(["amixer", "-c", card, "scontrols"],
                             capture_output=True, text=True, timeout=4).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    ctrls = re.findall(r"'([^']+)'", out)
    for pref in ("Master", "PCM", "Speaker", "Headphone", "Headphones", "Digital"):
        if pref in ctrls:
            return pref
    return ctrls[0] if ctrls else ""


def alsa_volume(card):
    """Current playback volume (0-100) of `card`'s main control, or None (#314)."""
    ctl = alsa_mixer_control(card)
    if not ctl:
        return None
    try:
        out = subprocess.run(["amixer", "-c", card, "sget", ctl],
                             capture_output=True, text=True, timeout=4).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"\[(\d+)%\]", out)
    return int(m.group(1)) if m else None


def set_alsa_volume(card, pct):
    """Set `card`'s main playback control to pct% (clamped 0-100) and unmute (#314).
    Returns True on success. This is the OUTPUT level, distinct from fluidsynth's
    synth.gain — david: 'on a le gain mais pas le volume'."""
    ctl = alsa_mixer_control(card)
    if not ctl:
        return False
    pct = max(0, min(100, int(pct)))
    try:
        r = subprocess.run(["amixer", "-c", card, "sset", ctl, f"{pct}%", "unmute"],
                           capture_output=True, timeout=4)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def midi_input_present():
    """True if any ALSA card exposes a MIDI input — i.e. the Keystation (or any
    USB-MIDI keyboard) is plugged in (#306). Drives the Home keyboard indicator.
    File-based (no aconnect subprocess): rawmidi shows up as /dev/snd/midiC*D* and
    as a midi* node under /proc/asound/card*/."""
    return bool(glob.glob("/dev/snd/midiC*D*")
                or glob.glob("/proc/asound/card*/midi*"))


def list_midi_inputs():
    """[(name, name)] of hardware MIDI input devices (USB-MIDI keyboards), from
    `aconnect -i` — clients carrying a `card=` (so System / Midi Through / FLUID Synth /
    PipeWire are excluded) (#326). Name is stable across reboots (client ids aren't), so
    it's both the key and the label."""
    try:
        out = subprocess.run(["aconnect", "-i"], capture_output=True, text=True, timeout=4).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    res = []
    for ln in out.splitlines():
        m = re.match(r"client\s+\d+\s*:\s*'(.+?)'\s*\[.*card=", ln)
        if m:
            res.append((m.group(1), m.group(1)))
    return res


def audio_output_present(soundcard="", bt_sink=""):
    """True if the active audio OUTPUT actually exists (#327): the chosen BT sink is
    connected, else the chosen ALSA card is present (or, on auto, any non-HDMI playback
    card). Drives the Home audio indicator — 'is there a working sound card?' — so it
    honestly dims if the USB interface drops."""
    if bt_sink:
        return any(mac == bt_sink for mac, _ in list_bt_sinks())
    cards = [c for c, _ in list_audio_cards()]
    return (soundcard in cards) if soundcard else bool(cards)


def audio_active():
    """True if piano.service (the synth) is running (#327). Drives the restart-done toast
    — more robust than the :9800 control port, which a busy/booting synth may not have
    bound yet."""
    try:
        return subprocess.run(["systemctl", "is-active", "piano.service"], capture_output=True,
                              text=True, timeout=4).stdout.strip() == "active"
    except (OSError, subprocess.SubprocessError):
        return False


def _pw_env():
    """Env to reach the user PipeWire session from the system service (#301/#314)."""
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return env


def _pw_dump():
    """Parsed `pw-dump` JSON, or [] when PipeWire isn't reachable (#301/#314)."""
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True,
                             timeout=5, env=_pw_env()).stdout
        return json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def list_bt_sinks():
    """[(mac, label), ...] of CONNECTED Bluetooth A2DP sinks exposed by PipeWire (#301).
    Nodes whose media.class is 'Audio/Sink' and node.name starts with 'bluez_output.'
    (`bluez_output.AA_BB_CC_DD_EE_FF.1`); the MAC is recovered from that name. The synth
    routes to one via fluidsynth's pulseaudio driver — see start-piano.sh. [] when
    PipeWire is unreachable or nothing is connected."""
    sinks = []
    for obj in _pw_dump():
        props = (obj.get("info") or {}).get("props") or {}
        name = props.get("node.name", "")
        if props.get("media.class") != "Audio/Sink" or not name.startswith("bluez_output."):
            continue
        try:
            mac = name.split(".")[1].replace("_", ":")     # bluez_output.AA_BB_..._FF.1 -> AA:BB:...:FF
        except IndexError:
            continue
        label = props.get("node.description") or props.get("device.description") or mac
        sinks.append((mac, label))
    return sinks


def _bt_sink_obj(mac):
    """The pw-dump Audio/Sink object for `mac`'s BT A2DP sink, or {} (#314)."""
    key = "bluez_output." + mac.replace(":", "_")
    for obj in _pw_dump():
        props = (obj.get("info") or {}).get("props") or {}
        if props.get("media.class") == "Audio/Sink" and props.get("node.name", "").startswith(key):
            return obj
    return {}


def _bt_sink_node(mac):
    """PipeWire node id of the connected BT A2DP sink for `mac`, or None — `wpctl`
    addresses nodes by id (#314)."""
    return _bt_sink_obj(mac).get("id")


def _bt_sink_name(mac):
    """PipeWire node.name of the BT sink for `mac` (e.g. bluez_output.AA_..._FF.1), or
    '' — `pw-play --target` wants the node NAME/serial, not the object id (#318)."""
    return ((_bt_sink_obj(mac).get("info") or {}).get("props") or {}).get("node.name", "")


def bt_volume(mac):
    """Current volume (0-100) of the BT sink for `mac` via `wpctl get-volume`, or None.
    Distinct from synth.gain — the A2DP output level (#314)."""
    nid = _bt_sink_node(mac)
    if nid is None:
        return None
    try:
        out = subprocess.run(["wpctl", "get-volume", str(nid)], capture_output=True,
                             text=True, timeout=4, env=_pw_env()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"Volume:\s*([\d.]+)", out)        # "Volume: 0.52" → 52
    return round(float(m.group(1)) * 100) if m else None


def set_bt_volume(mac, pct):
    """Set the BT sink for `mac` to pct% (clamped 0-100) via `wpctl set-volume` (#314)."""
    nid = _bt_sink_node(mac)
    if nid is None:
        return False
    pct = max(0, min(100, int(pct)))
    try:
        r = subprocess.run(["wpctl", "set-volume", str(nid), f"{pct}%"],
                           capture_output=True, timeout=4, env=_pw_env())
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def play_test(wav, soundcard="", bt_sink=""):
    """Fire-and-forget a short test sound on the ACTIVE output (#318), so the user can
    confirm a device works independently of the synth: BT sink → pw-play to its node,
    ALSA card → aplay -D plughw:<card>, else the system default. Returns True if a player
    was launched."""
    if not wav:
        return False
    try:
        if bt_sink:
            name = _bt_sink_name(bt_sink)        # pw-play --target = node NAME/serial, not id (#318)
            if name:
                subprocess.Popen(["pw-play", "--target", name, wav], env=_pw_env(),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        cmd = ["aplay", "-q"]
        if soundcard:
            cmd += ["-D", f"plughw:{soundcard}"]
        cmd.append(wav)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False
