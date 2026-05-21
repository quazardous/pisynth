#!/usr/bin/env bash
# setup.sh — kept for muscle memory. The real installer is the migration
# runner now: see apply.sh + migrations/. This just forwards to it.
#
#   sudo bash setup.sh        ==  sudo bash apply.sh
#
# From the laptop, prefer the one-shot:  ./deploy.sh
set -euo pipefail
exec bash "$(dirname "$(readlink -f "$0")")/apply.sh" "$@"
