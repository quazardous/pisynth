#!/bin/sh
# hdmi-connected.sh — exit 0 if any HDMI connector is plugged, 1 otherwise.
# Used as an ExecCondition= for lightdm so the Wayland desktop only starts
# when a screen is actually attached. Headless (synth + SPI screen) needs no
# desktop. Installed as /usr/local/bin/pisynth-hdmi-connected.
for f in /sys/class/drm/*HDMI*/status; do
    [ -f "$f" ] || continue
    [ "$(cat "$f")" = "connected" ] && exit 0
done
exit 1
