#!/usr/bin/env bash
# 023 — pisynth-web runs on aiohttp (#2428): HTTP, WebSocket and TLS from the Debian package
# instead of the hand-written server. sync.sh restarts the service with the new code.
# Revert: apt-get remove python3-aiohttp (and deploy a version before #2428)
set -euo pipefail

DEBIAN_FRONTEND=noninteractive apt-get install -y python3-aiohttp
python3 -c 'import aiohttp; print("[023] aiohttp", aiohttp.__version__)'
