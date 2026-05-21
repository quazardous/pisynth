#!/usr/bin/env bash
# 007 — keep the text console (fbcon) off the SPI panel so login/boot text
# doesn't bleed over the UI. The panel is the only framebuffer (fb0), so
# fbcon=map:1 sends the console to a non-existent fb1 — i.e. nowhere on screen.
set -euo pipefail

CMD=/boot/firmware/cmdline.txt
[[ -f "$CMD" ]] || CMD=/boot/cmdline.txt

if grep -qw "fbcon=map:1" "$CMD"; then
    echo "[007] fbcon=map:1 already set in $CMD"
else
    sed -i '1 s/$/ fbcon=map:1/' "$CMD"     # cmdline.txt is a single line
    echo "[007] added fbcon=map:1 to $CMD (reboot to apply)"
fi
