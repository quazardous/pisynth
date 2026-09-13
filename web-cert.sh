#!/usr/bin/env bash
# web-cert.sh → /usr/local/sbin/pisynth-web-cert — HTTPS for the web companion (#2427).
#
# pisynth runs its own small certificate authority, so a phone can trust pisynth once (install the
# CA) and never see a certificate warning again, whatever the Pi's IP becomes:
#   ca.pem / ca-key.pem   the CA (10 years). Name-constrained to the local network — *.local and
#                         private IPv4 ranges — so even installed on a phone it can't vouch for
#                         any internet site. The key is root-only.
#   cert.pem / key.pem    the server certificate pisynth-web uses, signed by the CA, for
#                         <hostname>.local + the Pi's current private IPs. Reissued when those
#                         change or it gets within 30 days of expiry (397-day validity).
#
#   pisynth-web-cert ensure        create what's missing / out of date (run before pisynth-web starts)
#   pisynth-web-cert fingerprint   SHA-256 of the CA, as the phone shows it
#
# Env (tests, dev): PISYNTH_WEB_CERT_DIR (/etc/pisynth/web), PISYNTH_CERT_HOST (hostname),
# PISYNTH_CERT_IPS (hostname -I), PISYNTH_CERT_GROUP (group that may read key.pem).
set -euo pipefail

DIR="${PISYNTH_WEB_CERT_DIR:-/etc/pisynth/web}"
HOST="${PISYNTH_CERT_HOST:-$(hostname)}"
IPS="${PISYNTH_CERT_IPS:-$(hostname -I 2>/dev/null || true)}"
GROUP="${PISYNTH_CERT_GROUP:-$(stat -c %G "$DIR/key.pem" 2>/dev/null || echo root)}"
CA_CONSTRAINTS="critical,permitted;DNS:local,permitted;IP:10.0.0.0/255.0.0.0,permitted;IP:172.16.0.0/255.240.0.0,permitted;IP:192.168.0.0/255.255.0.0"

private_ipv4() {   # the private IPv4 addresses among $IPS, sorted, one per line
    local ip
    for ip in $IPS; do
        case "$ip" in
            10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[01].*) echo "$ip" ;;
        esac
    done | sort -u
}

fingerprint() {
    openssl x509 -in "$DIR/ca.pem" -noout -fingerprint -sha256 | cut -d= -f2
}

ensure_ca() {
    [[ -s "$DIR/ca.pem" && -s "$DIR/ca-key.pem" ]] && return 0
    ( umask 077
      openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -sha256 -days 3650 \
          -keyout "$DIR/ca-key.pem" -out "$DIR/ca.pem" -subj "/O=pisynth/CN=pisynth local CA ($HOST)" \
          -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
          -addext "keyUsage=critical,keyCertSign,cRLSign" \
          -addext "nameConstraints=$CA_CONSTRAINTS" 2>/dev/null )
    chmod 0600 "$DIR/ca-key.pem"
    chmod 0644 "$DIR/ca.pem"
    echo "[web-cert] new CA, fingerprint $(fingerprint)"
}

ensure_cert() {
    local san="DNS:$HOST.local" ip
    for ip in $(private_ipv4); do san="$san,IP:$ip"; done
    if [[ -s "$DIR/cert.pem" && -s "$DIR/key.pem" && "$(cat "$DIR/cert.san" 2>/dev/null)" == "$san" ]] \
        && openssl verify -CAfile "$DIR/ca.pem" "$DIR/cert.pem" >/dev/null 2>&1 \
        && openssl x509 -in "$DIR/cert.pem" -noout -checkend 2592000 >/dev/null; then
        echo "[web-cert] certificate up to date ($san)"
        return 0
    fi
    local tmp; tmp="$(mktemp -d "$DIR/.issue.XXXXXX")"
    printf 'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=%s\n' "$san" > "$tmp/ext"
    ( umask 077
      openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
          -keyout "$tmp/key.pem" -out "$tmp/req.csr" -subj "/O=pisynth/CN=$HOST.local" 2>/dev/null )
    openssl x509 -req -in "$tmp/req.csr" -CA "$DIR/ca.pem" -CAkey "$DIR/ca-key.pem" -set_serial "0x$(openssl rand -hex 16)" \
        -days 397 -sha256 -extfile "$tmp/ext" -out "$tmp/cert.pem" 2>/dev/null
    chgrp "$GROUP" "$tmp/key.pem" 2>/dev/null || true
    chmod 0640 "$tmp/key.pem"
    chmod 0644 "$tmp/cert.pem"
    mv -f "$tmp/key.pem" "$DIR/key.pem"
    mv -f "$tmp/cert.pem" "$DIR/cert.pem"
    printf '%s' "$san" > "$DIR/cert.san"
    rm -rf "$tmp"
    echo "[web-cert] issued the server certificate for $san"
}

case "${1:-ensure}" in
    ensure)
        install -d -m 0755 "$DIR"
        ensure_ca
        ensure_cert ;;
    fingerprint)
        fingerprint ;;
    *)
        echo "usage: pisynth-web-cert ensure|fingerprint" >&2; exit 2 ;;
esac
