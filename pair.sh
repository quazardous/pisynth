#!/usr/bin/env bash
# pair.sh — a one-time pairing link for the web companion running ON the Pi, from your computer.
# Same as tapping the QR icon on the pisynth screen, without being at the box.
# Usage:
#   ./pair.sh          print the link (valid 2 min, single use)
#   ./pair.sh --open   and open it in your default browser
#   ./pair.sh --qr     and draw it as a QR code in the terminal (needs python3-segno)
# Only ONE browser is paired at a time: using the link unpairs the previous one (e.g. your phone).
# The Pi's certificate is self-signed: the browser warns the first time, accept it.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
for c in "$REPO_DIR/pisynth.conf" "$REPO_DIR/pisynth.conf.dist"; do
    [ -n "${PISYNTH_HOST:-}" ] && break
    [ -f "$c" ] && . "$c"
done
PI="${PISYNTH_HOST:-pi@raspberrypi.local}"
HOST="${PI#*@}"

# The admin API only listens on the Pi's loopback: ask for a token over SSH.
json="$(ssh "$PI" 'curl -fsS -X POST http://127.0.0.1:9811/admin/token')" \
    || { echo "pair.sh: no token from pisynth-web on $PI (is the service running?)" >&2; exit 1; }
read -r token port ttl < <(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["token"], d["port"], d["ttl"])' <<<"$json")
url="https://$HOST:$port/#k=$token"

echo "$url"
echo "valid ${ttl} s · single use · pairing it unpairs the browser paired before" >&2
case "${1:-}" in
    --open) xdg-open "$url" >/dev/null 2>&1 || open "$url" 2>/dev/null || echo "pair.sh: open it by hand" >&2 ;;
    --qr)   python3 -c 'import segno,sys; segno.make(sys.argv[1], error="m").terminal(compact=True)' "$url" \
                || echo "pair.sh: install segno (pip install segno) for the QR code" >&2 ;;
esac
