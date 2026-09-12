#!/usr/bin/env bash
# 022 — web companion (#659): the pisynth-web service a paired phone talks to.
#  - python3-segno (QR code on the touch screen) and openssl
#  - a self-signed TLS certificate (the phone's microphone and service worker need HTTPS);
#    generated once, kept across deploys: /etc/pisynth/web/{cert,key}.pem
#  - enable pisynth-web.service (unit installed by sync.sh on every deploy)
# Revert: systemctl disable --now pisynth-web; rm -r /etc/pisynth/web
set -euo pipefail

DEBIAN_FRONTEND=noninteractive apt-get install -y python3-segno openssl

DIR=/etc/pisynth/web
install -d -m 0755 /etc/pisynth "$DIR"
if [[ ! -s "$DIR/cert.pem" ]]; then
    host="$(hostname)"
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
        -keyout "$DIR/key.pem" -out "$DIR/cert.pem" -days 3650 \
        -subj "/CN=$host" -addext "subjectAltName=DNS:$host,DNS:$host.local" 2>/dev/null
    echo "[022] generated $DIR/cert.pem for $host"
fi
chown root:root "$DIR/cert.pem" && chmod 0644 "$DIR/cert.pem"
chown "root:$(id -gn "$TARGET_USER")" "$DIR/key.pem" && chmod 0640 "$DIR/key.pem"   # readable by the service user only
echo "[022] fingerprint: $(openssl x509 -in "$DIR/cert.pem" -noout -fingerprint -sha256 | cut -d= -f2)"

install -m 0644 "$REPO_DIR/pisynth-web.service" /etc/systemd/system/pisynth-web.service
sed -i -E "s/^User=.*/User=$TARGET_USER/" /etc/systemd/system/pisynth-web.service
systemctl daemon-reload
systemctl enable pisynth-web.service
echo "[022] pisynth-web enabled (started by sync.sh)"
