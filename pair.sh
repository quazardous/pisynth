#!/usr/bin/env bash
# pair.sh — a one-time pairing link for the web companion running ON the Pi, from your computer.
# Same as tapping the QR icon on the pisynth screen, without being at the box.
# Usage:
#   ./pair.sh          print the link (valid 2 min, single use)
#   ./pair.sh --open   and open it in your default browser
#   ./pair.sh --qr     and draw it as a QR code in the terminal (needs python3-segno)
#   ./pair.sh --ca     download pisynth's certificate authority (pisynth-ca.crt) to trust it here
# Only ONE browser is paired at a time: using the link unpairs the previous one (e.g. your phone).
# The link opens pisynth's setup page (#2427): straight to the app if this browser already trusts
# pisynth's CA, otherwise it explains how to install it.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
for c in "$REPO_DIR/pisynth.conf" "$REPO_DIR/pisynth.conf.dist"; do
    [ -n "${PISYNTH_HOST:-}" ] && break
    [ -f "$c" ] && . "$c"
done
PI="${PISYNTH_HOST:-pi@raspberrypi.local}"
HOST="${PI#*@}"

if [[ "${1:-}" == "--ca" ]]; then
    ssh "$PI" 'cat /etc/pisynth/web/ca.pem' > pisynth-ca.crt \
        || { echo "pair.sh: no CA on $PI yet (deploy first)" >&2; rm -f pisynth-ca.crt; exit 1; }
    echo "saved pisynth-ca.crt · SHA-256 $(openssl x509 -in pisynth-ca.crt -noout -fingerprint -sha256 | cut -d= -f2)"
    cat >&2 <<'EOF'
Trust it in your browser (it can only vouch for .local names and private IPs):
  Chrome/Edge  Settings → Privacy and security → Security → Manage certificates → Custom → Installed by you → Import
  Firefox      Settings → Privacy & Security → Certificates → View Certificates → Authorities → Import
  Linux system sudo trust anchor pisynth-ca.crt        (Fedora/Arch; Debian: copy to /usr/local/share/ca-certificates + update-ca-certificates)
EOF
    exit 0
fi

# The admin API only listens on the Pi's loopback: ask for a token over SSH.
json="$(ssh "$PI" 'curl -fsS -X POST http://127.0.0.1:9811/admin/token')" \
    || { echo "pair.sh: no token from pisynth-web on $PI (is the service running?)" >&2; exit 1; }
read -r token port ttl setup < <(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["token"], d["port"], d["ttl"], d.get("setup_port", ""))' <<<"$json")
if [[ -n "$setup" ]]; then
    url="http://$HOST:$setup/#k=$token"
else
    url="https://$HOST:$port/#k=$token"
fi

echo "$url"
echo "valid ${ttl} s · single use · pairing it unpairs the browser paired before" >&2
case "${1:-}" in
    --open) xdg-open "$url" >/dev/null 2>&1 || open "$url" 2>/dev/null || echo "pair.sh: open it by hand" >&2 ;;
    --qr)   python3 -c 'import segno,sys; segno.make(sys.argv[1], error="m").terminal(compact=True)' "$url" \
                || echo "pair.sh: install segno (pip install segno) for the QR code" >&2 ;;
esac
