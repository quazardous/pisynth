#!/usr/bin/env bash
# wifi-connect.sh — helper to connect the R4S to a WiFi network via NetworkManager.
# Usage:
#   sudo bash /home/pi/piano/wifi-connect.sh                 # interactive (scans + asks)
#   sudo bash /home/pi/piano/wifi-connect.sh "SSID" "PASS"   # non-interactive

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run as root: sudo bash $0"
    exit 1
fi

echo "[wifi] looking for a WiFi interface..."
WIFI_IF="$(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2=="wifi"{print $1; exit}')"

if [[ -z "${WIFI_IF:-}" ]]; then
    echo "[wifi] no WiFi interface found. Is the USB dongle plugged in?"
    echo "[wifi] lsusb output:"
    lsusb
    echo "[wifi] if your dongle appears above but no WiFi interface shows up,"
    echo "       you probably need a firmware package. Try:"
    echo "       sudo apt install firmware-realtek firmware-iwlwifi firmware-atheros firmware-brcm80211 firmware-misc-nonfree"
    exit 1
fi
echo "[wifi] found WiFi device: $WIFI_IF"

nmcli radio wifi on

if [[ $# -ge 2 ]]; then
    SSID="$1"; PASS="$2"
    echo "[wifi] connecting to '$SSID'..."
    nmcli dev wifi connect "$SSID" password "$PASS" ifname "$WIFI_IF"
else
    echo "[wifi] scanning... (gives 3s)"
    nmcli dev wifi rescan ifname "$WIFI_IF" || true
    sleep 3
    nmcli dev wifi list ifname "$WIFI_IF"
    echo
    read -rp "SSID to connect to: " SSID
    read -rsp "Password: " PASS
    echo
    nmcli dev wifi connect "$SSID" password "$PASS" ifname "$WIFI_IF"
fi

echo "[wifi] connection saved (will auto-reconnect at boot)."
echo "[wifi] current IP addresses:"
ip -brief addr show "$WIFI_IF"
