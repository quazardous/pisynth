# Roadmap

Planned and deferred work for pisynth. Items listed here are **not yet implemented**.

## Hardware mods

### Software-controllable screen backlight (#277)

The bundled 3.5" goodtft display (ILI9486 + ADS7846, `dtoverlay=piscreen`) wires its
LED backlight **permanently on** — it cannot be switched off in software. Confirmed on
the reference unit:

- the `fb_ili9486` backlight is a stub: `/sys/class/backlight/fb_ili9486/max_brightness`
  is `0`, and writing `bl_power` has no effect on the LED;
- the two documented candidate enable pins, BCM **GPIO18** and **GPIO22** (physical
  pin 15, the `tft35a` `backlight=15` pin), toggle at the register level without
  affecting the LED.

Many cheap 3.5" clones are built this way. As a result the screen-sleep feature
(Settings → Screen sleep) can only blank the framebuffer to black; it does **not** cut
the backlight or save power.

**Planned fix (hardware):** splice a small N-channel MOSFET (e.g. AO3400) or NPN
transistor (e.g. 2N2222) into the backlight LED supply line and gate it from a free
GPIO. The UI's `Backlight` class would then drive that GPIO (replacing the no-op
`bl_power` path), and a migration would grant the run-as user access to it. This
requires fine soldering on the panel PCB.

References:
- <https://community.victronenergy.com/questions/146206/cheap-35-tft-touchscreen-backlight-raspberry-pi-mo.html>
- <https://s0n1c3.wordpress.com/2024/05/25/3-5-resistive-touchscreen-backlight-control/>

## Performance tuning

The original NanoPi build shipped an `optimize.sh` that we dropped because it was
RK3399-specific (it pinned fluidsynth to the A72 "big" cores). The Pi 3B+ has four
identical Cortex-A53 cores, so CPU-affinity pinning buys nothing. But two of its ideas
still apply and could be brought back as a Pi-appropriate, opt-in tweak:

- **Force the CPU governor to `performance`** (boot-persistent via a small systemd unit)
  so the cores don't down-clock under the on-demand governor — fewer audio xruns at the
  cost of more idle power.
- **Move journald to RAM** (`Storage=volatile`) to avoid SD-card writes during play
  (less wear; logs don't survive reboot).

Not needed: CPU pinning (no big.LITTLE on the 3B+). `piano.service` already requests
real-time scheduling (`LimitRTPRIO`, `Nice=-10`, realtime IO). Ship as a reversible,
opt-in migration if/when xruns are observed on hardware.
