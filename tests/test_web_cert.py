"""web-cert.sh (#2427): pisynth's local CA and the server certificate it signs, on a temp dir —
the certificate validates against the CA, covers <host>.local and the private IPs only, is
reissued when they change, and the CA's name constraints refuse anything outside the LAN."""
import grp
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "web-cert.sh"
pytestmark = pytest.mark.skipif(shutil.which("openssl") is None or shutil.which("bash") is None,
                                reason="needs bash + openssl")


def run(d, ips, *args):
    env = {**os.environ, "PISYNTH_WEB_CERT_DIR": str(d), "PISYNTH_CERT_HOST": "pisynth",
           "PISYNTH_CERT_IPS": ips, "PISYNTH_CERT_GROUP": grp.getgrgid(os.getgid()).gr_name}
    r = subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def openssl(*args, check=True):
    return subprocess.run(["openssl", *args], capture_output=True, text=True, check=check)


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_ca_signs_a_lan_certificate_and_reissues_only_when_needed(tmp_path):
    d = tmp_path / "web"
    out = run(d, "192.168.50.23 172.17.0.1 8.8.8.8 127.0.0.1 fe80::1")
    assert "new CA" in out and "issued" in out
    assert oct((d / "ca-key.pem").stat().st_mode)[-3:] == "600" and oct((d / "key.pem").stat().st_mode)[-3:] == "640"
    assert openssl("verify", "-CAfile", str(d / "ca.pem"), str(d / "cert.pem")).stdout.strip().endswith("OK")
    san = openssl("x509", "-in", str(d / "cert.pem"), "-noout", "-ext", "subjectAltName").stdout
    assert "DNS:pisynth.local" in san and "IP Address:192.168.50.23" in san and "IP Address:172.17.0.1" in san
    assert "8.8.8.8" not in san and "127.0.0.1" not in san
    ca_text = openssl("x509", "-in", str(d / "ca.pem"), "-noout", "-text").stdout
    assert "Name Constraints: critical" in ca_text and "CA:TRUE, pathlen:0" in ca_text

    ca, cert = digest(d / "ca.pem"), digest(d / "cert.pem")
    assert "up to date" in run(d, "192.168.50.23 172.17.0.1")               # same private IPs: untouched
    assert digest(d / "cert.pem") == cert
    assert "issued" in run(d, "192.168.50.77")                                # the IP changed
    assert digest(d / "ca.pem") == ca and digest(d / "cert.pem") != cert    # same CA: the phone still trusts it
    assert "IP Address:192.168.50.77" in openssl("x509", "-in", str(d / "cert.pem"), "-noout", "-ext", "subjectAltName").stdout
    assert run(d, "", "fingerprint").strip().count(":") == 31


def test_name_constraints_refuse_a_certificate_for_an_internet_site(tmp_path):
    d = tmp_path / "web"
    run(d, "192.168.50.23")
    key, csr, crt, ext = (tmp_path / n for n in ("evil.key", "evil.csr", "evil.pem", "evil.ext"))
    ext.write_text("subjectAltName=DNS:www.example.com\n")
    openssl("req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
            "-keyout", str(key), "-out", str(csr), "-subj", "/CN=www.example.com")
    openssl("x509", "-req", "-in", str(csr), "-CA", str(d / "ca.pem"), "-CAkey", str(d / "ca-key.pem"),
            "-set_serial", "7", "-days", "30", "-extfile", str(ext), "-out", str(crt))
    r = openssl("verify", "-CAfile", str(d / "ca.pem"), str(crt), check=False)
    assert r.returncode != 0 and "permitted subtree" in (r.stdout + r.stderr)
