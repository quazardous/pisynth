#!/usr/bin/env bash
# 021 — let the touch UI write its preferences / Bluetooth pairings through a read-only
# root (#681 phase B): a sudoers grant scoped to ONE root helper sub-command,
# `pisynth-readonly persist`, which only accepts a fixed whitelist of paths.
# Harmless when the read-only root is off (persist is then a no-op).
# Revert: rm /etc/sudoers.d/pisynth-readonly-persist
set -euo pipefail

f=/etc/sudoers.d/pisynth-readonly-persist      # no '.' in the name: sudo skips such files
tmp="$(mktemp)"
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/pisynth-readonly persist *\n' "$TARGET_USER" > "$tmp"
visudo -cf "$tmp"
install -m 0440 -o root -g root "$tmp" "$f"
rm -f "$tmp"
echo "[021] $f: $TARGET_USER may run 'pisynth-readonly persist' as root"
