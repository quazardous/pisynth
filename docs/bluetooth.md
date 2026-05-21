# Bluetooth

> Status (ticket #287): **pairing manager implemented** — the Settings → Audio → Bluetooth
> screen, a `bluetoothctl` backend (`Bluetooth` in `ui/pisynth-ui.py`), and a polkit grant
> (migration 011) are in. The device list / parsing is validated against real BlueZ; **scan
> + pairing of audio devices still need on-device validation**. Not yet done: routing a BT
> sink as the metronome output, and **BLE-MIDI** input.

pisynth can use Bluetooth for two things:

- **Audio output** — send sound (e.g. the metronome click) to a Bluetooth speaker/headset.
- **BLE-MIDI input** — connect a wireless MIDI keyboard / controller / pedal.

Both are managed from one place: **Settings → Audio → Bluetooth** (the pairing manager).

## Stack on the Pi

| Piece | Used for |
|---|---|
| BlueZ (`bluetoothctl`, `bluetoothd`) | pairing, connection, trust |
| PipeWire (`pw-play`) | playing audio to a connected Bluetooth **sink** |
| ALSA sequencer (`aconnect`, `aseqdump`) | a connected BLE-**MIDI** device's input port |

The Pi 3B+ has an onboard Bluetooth controller and the `bluetooth` service is active by default.

## Pairing flow (cinématique)

**Settings → Audio → Bluetooth:**

```
‹  Bluetooth                    ◀ Scan
 ● Sony WH-1000XM4      connected     ← marked (yellow) = active
   JBL Flip 5           paired
   Pierre's Buds        available     ← appears while scanning
```

1. Open the screen → the controller is powered on (`power on`); paired devices are listed.
2. **Scan** (toggle) → `scan on` in the background; the list refreshes every ~2 s
   (`devices` / `info`) and adds newly discovered devices by name. Tap again to stop.
3. Tap an **available** device → `pair → trust → connect`, with footer states
   ("Pairing <name>…" → "Connected ✓" / "Failed").
4. A connected device is then usable:
   - **audio sink** → it becomes a PipeWire sink, selectable as the metronome's (and
     optionally the synth's) output, played via `pw-play`;
   - **BLE-MIDI** → it exposes an ALSA seq port, which fluidsynth grabs via
     `midi.autoconnect=1` (same path as a USB MIDI keyboard, cable-free).
5. **Paired** devices are *trusted*, so they **auto-reconnect** on boot / in range. Tap to
   connect or disconnect.
6. **Forget**: long-press → `remove <mac>`.

Under the hood: scripted `bluetoothctl` subcommands (`power on`, `scan on/off`, `devices`,
`info`, `pair`, `trust`, `connect`, `disconnect`, `remove`) — no extra library.

## Audio output & latency

A connected speaker/headset is an A2DP **sink**. Bluetooth A2DP adds **~100–200 ms of
latency** (and it varies by device). Fine for casual listening, but poor for a **metronome**
(a timing reference) or for **playing the synth live** — the click/notes lag and drift. So:

- Default the metronome/synth output to a **wired** card (onboard jack or USB interface).
- Offer Bluetooth as an **optional** output, not the default. The latency is the user's
  call — pisynth does not try to compensate for it.

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
  management of `org.bluez` will likely be needed (same pattern as the audio-restart grant,
  ticket #282).

## See also

- [roadmap.md](roadmap.md) — planned / deferred work.
- Ticket #287 (metronome) — where this was designed.
