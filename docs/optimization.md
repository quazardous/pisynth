# Optimizing the Pi for fluidsynth

How to get the cleanest, lowest-latency synth out of the reference hardware
(**Raspberry Pi 3B+**, fluidsynth driving a USB audio interface via direct ALSA).
"Good" here means: **no xruns/crackles**, low note-to-sound latency, and enough CPU
headroom for dense chords without dropouts.

> **The single most important thing:** on a Pi 3B+ the ceiling is almost always
> **power and cooling**, not software. If the board under-volts or overheats it drops
> its clock, and *no* fluidsynth tuning survives a throttle. Fix the hardware first,
> then tune.

## 0. Know before you tune — measure

Tuning blind is guessing. The handful of commands that tell you what's actually going on
(all read-only; run them via `./probe.sh '<cmd>'` from the laptop):

| Question | Command | You want |
|----------|---------|----------|
| Has the board throttled/under-volted? | `vcgencmd get_throttled` | `0x0` |
| Temperature? | `vcgencmd measure_temp` | well under 60 °C |
| Is the CPU at full clock? | `vcgencmd measure_clock arm` | `1400000000` |
| Governor? | `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor` | `performance` |
| Is the audio thread real-time? | `chrt -p <fluidsynth audio tid>` | `SCHED_FIFO` |
| Buffer underruns? | `cat /proc/asound/card*/pcm0p/sub0/status` | `xruns: 0` |
| Per-core load under play | `top -H` | no single core pinned at 100 % |

`vcgencmd get_throttled` is a bitmask: low bits (`0x1` under-voltage, `0x4` throttled now)
mean it is happening *right now*; high bits (`0x10000` under-voltage, `0x40000` throttling,
`0x80000` soft temp limit) mean it *has happened since boot*. Anything non-zero is a red flag.
The UI's **System → Health** page already surfaces throttle / under-voltage.

*Reference unit, observed:* `get_throttled = 0xd0000` — under-voltage, throttling **and**
the soft temp limit had all occurred (≥60 °C reached), governor was `ondemand`, audio was
`S24_3LE @ 44100` (no resampling). i.e. real headroom was being lost to power/heat.

## Tier 0 — Hardware (the real ceiling)

- **Power.** Use a genuine **5 V / 3 A** supply and a short, thick cable. USB interfaces and
  the screen draw real current; a marginal phone charger is the #1 cause of under-voltage
  throttling. Confirm with `get_throttled` after a session.
- **Cooling.** Add a heatsink, and a small fan if the case is enclosed. The Pi 3B+ starts
  reducing its clock at the soft temp limit (~60 °C). Sustained polyphony plus the SPI
  screen will get there in a warm room.

No software setting beats a board that isn't throttling.

## Tier 1 — CPU & scheduling (big, safe wins)

- **CPU governor → `performance`.** The default `ondemand`/`schedutil` scales the clock down
  when idle and ramps up on demand; that ramp adds latency and jitter exactly on the
  transient when you hit a chord. Locking `performance` pins 1.4 GHz.
- **`synth.cpu-cores=2`.** fluidsynth renders voices on **one** core by default. The 3B+ has
  four identical Cortex-A53 cores — letting it use two roughly doubles polyphony headroom.
  Three is possible but leaves only one core for the UI, IRQs and the system; two is the safe
  default.
- **Real-time audio thread.** The `piano.service` unit already grants the capability
  (`LimitRTPRIO=95`, `LimitMEMLOCK=infinity`, `Nice=-10`). fluidsynth requests `SCHED_FIFO`
  on its audio thread via `audio.realtime-prio` (default 60). Set it explicitly on the ALSA
  path and verify with `chrt -p` under load that the audio thread really is FIFO — a
  non-RT audio thread will glitch under any system hiccup.

## Tier 2 — Trim the system (less CPU, less jitter)

- **Disable services an appliance doesn't need.** On the reference image these were running
  for nothing: `rpcbind`, `nfs-blkmap`, `udisks2`, `accounts-daemon`, `avahi-daemon` (and
  `bluetooth` if you never use a Bluetooth speaker). Each is a background wakeup source;
  removing them frees RAM and reduces scheduling jitter.
- **`vm.swappiness=10`** (or disable swap entirely). With ~600 MB free there is no reason to
  page to the SD card mid-note — an SD stall is an instant dropout.
- **Reverb.** `synth.reverb.active` is the most expensive built-in effect (chorus is already
  off). For maximum headroom, turn it off; keep it on if you prefer the sound and have the
  CPU. Worth exposing as a setting.
- **`synth.polyphony`.** The default cap is 256 voices. Lowering it (e.g. 128) bounds the
  worst-case CPU spike at the cost of voice-stealing in very dense passages. Optional, and
  less necessary once `cpu-cores=2` is in.

## Tier 3 — USB / IRQ (Pi 3B+ specific, measure first)

The 3B+ hangs **everything** — the USB audio interface, the MIDI keyboard *and* the wired
Ethernet (`lan78xx`) — off a single `dwc_otg` USB 2.0 controller through the built-in hub.
Heavy traffic on one starves the others, which shows up as audio dropouts.

- If you run on **Wi-Fi, disable the wired Ethernet** so the audio interface isn't sharing
  the bus with network traffic.
- Avoid USB mass-storage activity while playing.
- Advanced: `threadirqs` plus pinning the USB IRQ to a core, or `isolcpus=3` to dedicate a
  core to the audio thread (with matching CPU affinity). Only worth it if measurement shows
  IRQ contention — don't cargo-cult it.

## Tier 4 — Latency (only once it's stable)

The ALSA buffer is `audio.period-size` × `audio.periods` frames (default **256 × 4** ≈ 23 ms
total, ~6 ms per period at 44.1 kHz). Smaller = lower latency, higher xrun risk.

- Drop `period-size` to 128 (~3 ms) **only after** power, cooling and governor are sorted and
  `get_throttled` reads `0x0` under load. On a throttling board, a smaller buffer just
  crackles sooner — raise it (512) instead until the hardware is fixed.
- Match the interface's native rate to avoid resampling (the reference M-Track is 44.1 kHz,
  which already matches fluidsynth's default — no resampling cost). `plughw:` is used so the
  interface's required `S24_3LE` format is handled transparently.

## Quick reference

| Lever | Default | Suggested | Where |
|-------|---------|-----------|-------|
| PSU / cooling | — | 5 V/3 A + heatsink | hardware |
| CPU governor | `ondemand` | `performance` | system (migration) |
| `synth.cpu-cores` | 1 | 2 | `start-piano.sh` |
| `audio.realtime-prio` | 60 (implicit) | 60 (explicit) + verify | `start-piano.sh` |
| Unused services | running | disabled | system (migration) |
| `vm.swappiness` | 60 | 10 | system (migration) |
| `synth.reverb.active` | on | off for max headroom | `start-piano.sh` / setting |
| `synth.polyphony` | 256 | 128 (optional) | `start-piano.sh` |
| `audio.period-size` | 256 | 128 once stable | `synth.conf` |

Already in place (baseline): RT scheduling + memlock on `piano.service`, `CPUQuota=200%`,
ALSA-direct output, `synth.dynamic-sample-loading=1`, one-soundfont-resident mode (#334),
PipeWire masked off the USB card.
