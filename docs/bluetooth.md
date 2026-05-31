# Bluetooth

> Status: **pairing manager + per-device menu + friendly names** implemented
> (Settings → Connectivity → Bluetooth devices; `bluetoothctl` backend in `ui/pisynth-ui.py`;
> polkit grant in migration 011). **Synth A2DP output** is implemented: pick a BT sink
> in Settings → Audio, persisted as `bluetooth.audio_sink`; `start-piano.sh` routes fluidsynth
> through pipewire-pulse, ALSA-direct otherwise. **Still needs on-device validation**: real
> XM4 pairing/bonding, the actual A2DP audio + latency, and linger at headless boot. Not yet
> done: **BLE-MIDI** input.

pisynth can use Bluetooth for two things:

- **Audio output** — send sound (e.g. the metronome click) to a Bluetooth speaker/headset.
- **BLE-MIDI input** — connect a wireless MIDI keyboard / controller / pedal.

Both are managed from one place: **Settings → Connectivity → Bluetooth devices** (the pairing manager).

## Stack on the Pi

| Piece | Used for |
|---|---|
| BlueZ (`bluetoothctl`, `bluetoothd`) | pairing, connection, trust |
| PipeWire + `pipewire-pulse` | exposing a connected BT **sink** (`bluez_output.<MAC>.N`); the synth routes to it via fluidsynth's `pulseaudio` driver, the metronome via `pw-play` |
| ALSA sequencer (`aconnect`, `aseqdump`) | a connected BLE-**MIDI** device's input port |

PipeWire/wireplumber/pipewire-pulse already run in the user session (no install needed);
`pactl` is **not** present, so the synth targets the sink by node-name via fluidsynth's
`pulseaudio` driver rather than `pactl`. `pw-dump` resolves the live sink name.

The Pi 3B+ has an onboard Bluetooth controller and the `bluetooth` service is active by default.

## Pairing flow (cinématique)

**Settings → Connectivity → Bluetooth devices:**

```
‹  Bluetooth                    ◀ Scan
 ● Sony WH-1000XM4      connected  › ← marked (yellow) = active
   JBL Flip 5           paired     ›
   Pierre's Buds        not paired › ← appears while scanning
```

1. Open the screen → the controller is powered on (`power on`); known/paired devices are listed.
2. **Scan** (toggle) → `scan on` in the background; the list refreshes every ~2 s
   (`devices` / `info`) and adds newly discovered devices by name. Tap again to stop.
3. **Each device is a menu**: tap a device → its own screen with the contextual
   action + **Forget** + Status/Address:
   - **not paired** → *Pair & connect* (`pair → trust → connect`),
   - **paired** → *Connect*, **connected** → *Disconnect*,
   - **Forget** → confirm → `remove <mac>`.
   Status is spelled **not paired / paired / connected** ("available" was ambiguous).
4. A connected device is then usable:
   - **audio sink** → it becomes a PipeWire sink. Pick it as the **synth** output in
     **Settings → Audio → Audio device** (it appears alongside the ALSA cards, tagged
     `BT`); see *Synth output to a BT sink* below. The metronome can also target it via
     `pw-play`.
   - **BLE-MIDI** → it exposes an ALSA seq port, which fluidsynth grabs via
     `midi.autoconnect=1` (same path as a USB MIDI keyboard, cable-free).
5. **Paired** devices are *trusted*, so they **auto-reconnect** on boot / in range.
6. **Friendly names** are resolved via `bluetoothctl info` (Alias) and remembered in
   `settings.yaml` (`bluetooth.known`), so known devices keep a name even with scan
   off or before BlueZ re-resolves it — never a bare MAC once seen.

Under the hood: scripted `bluetoothctl` subcommands (`power on`, `scan on/off`, `devices`,
`info`, `pair`, `trust`, `connect`, `disconnect`, `remove`) — no extra library.

## Audio output & latency

A connected speaker/headset is an A2DP **sink**. Bluetooth A2DP adds **~100–200 ms of
latency** (and it varies by device). Fine for casual listening, but poor for a **metronome**
(a timing reference) or for **playing the synth live** — the click/notes lag and drift. So:

- Default the metronome/synth output to a **wired** card (onboard jack or USB interface).
- Offer Bluetooth as an **optional** output, not the default. The latency is the user's
  call — pisynth does not try to compensate for it.

### Synth output to a BT sink

The audio-device picker lists connected A2DP sinks below the ALSA cards (tagged `BT`).
Choosing one persists its MAC to `settings.yaml` as `bluetooth.audio_sink` and clears
`soundcard` (exactly one output is active); choosing an ALSA card / *Auto* clears it again.

`start-piano.sh` reads `bluetooth.audio_sink`:

- **empty (default)** → fluidsynth runs **ALSA-direct** on the USB card, never touching
  PipeWire — *"if no BT device is in use, only ALSA is brought up"*.
- **set** → fluidsynth runs with `--audio-driver=pulseaudio` and
  `audio.pulseaudio.device=bluez_output.<MAC>.N` (resolved live from `pw-dump`). It waits
  up to `BT_WAIT` (20 s) for the trusted sink to (auto-)connect, then **falls back to ALSA**
  if it never appears, so there is always sound.

Because `start-piano.sh` runs as a *system* service, it exports
`XDG_RUNTIME_DIR=/run/user/<uid>` to reach the user PipeWire graph, and migration
`015-linger.sh` runs `loginctl enable-linger` so that graph is up at headless boot (nobody
logs in on an appliance).

## BLE-MIDI

Wireless MIDI keyboards, controllers and expression/sustain pedals increasingly speak
**BLE-MIDI**. Once connected, the device shows up as an ALSA sequencer port and feeds
fluidsynth like a USB keyboard — no cable.

**Requires enabling BlueZ's MIDI plugin**, which is **experimental and off by default**. A
migration would set, in `/etc/bluetooth/main.conf`:

```ini
[General]
Experimental = true
```

(and ensure the `midi` plugin is loaded), then restart `bluetooth`. Verify with
`aconnect -i` / `aseqdump`. BLE-MIDI on Linux works but can be finicky depending on the
device — to be validated on hardware.

## Gotchas

- **Touch-only ⇒ "Just Works" pairing only.** There's no keyboard for a PIN/passkey, so
  devices that require one can't be paired from the screen. Virtually all A2DP audio and
  BLE-MIDI gear uses Just Works, so this is rarely a problem (the UI shows a clear message
  otherwise).
- **Service permissions.** The UI runs as a systemd service (`User=<run-as user>`); driving
  BlueZ (pair/connect) as non-root goes through **polkit**. A migration granting that user
  management of `org.bluez` will likely be needed (same pattern as the audio-restart grant).

## See also

- [roadmap.md](roadmap.md) — planned / deferred work.
