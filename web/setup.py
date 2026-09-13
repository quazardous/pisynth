"""The setup page (#2427): plain HTTP, served on the LAN by pisynth-web, where the pairing QR lands.

It checks whether this phone already trusts pisynth's certificate authority (a no-cors fetch to
the HTTPS app succeeds only if the certificate is trusted): if so it forwards to the app right
away, keeping the one-time pairing code in the #fragment (never sent to a server). If not, it
explains how to install the CA once, with the fingerprint to compare with the pisynth screen — and
lets the phone go on without it: the browser warns once, and the app works all the same.
The page serves nothing else: no API, no session.
"""
import html

CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https:; "
       "img-src 'self' data:; frame-ancestors 'none'")

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Set up pisynth</title>
<style>
  body {{ margin: 0; font: 16px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: #121218; color: #ebebf0; }}
  main {{ max-width: 34rem; margin: 0 auto; padding: 20px 16px 40px; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 12px; }}
  h2 {{ font-size: 1.05rem; margin: 22px 0 6px; }}
  .card {{ background: #22222e; border-radius: 12px; padding: 14px 16px; margin-top: 12px; }}
  a.button, button {{ display: inline-block; margin-top: 10px; font: inherit; font-weight: 700; padding: 12px 20px; border: 0;
                      border-radius: 10px; background: #5aa0ff; color: #fff; text-decoration: none; }}
  a.button.secondary {{ background: #3a3a48; }}
  .muted {{ color: #9a9eae; font-size: .92rem; }}
  code {{ font-size: .85rem; word-break: break-all; color: #ffd23f; }}
  ol {{ padding-left: 1.2rem; }} li {{ margin: 4px 0; }}
</style></head>
<body data-port="{port}">
<main>
  <h1>Set up pisynth on this phone</h1>
  <p id="status">Checking the certificate…</p>
  <p id="nopair" class="muted" hidden>No pairing code in this link: open it from the QR code on the pisynth screen.</p>

  <div id="steps" hidden>
    <div class="card">
      <h2>In a hurry? Continue without installing</h2>
      <a class="button secondary" id="anyway" href="#">Open pisynth anyway</a>
      <p class="muted">Your browser will say the connection isn't private: that's only because it doesn't know
        pisynth's certificate yet. Choose <b>Advanced → Continue</b> (Android) or <b>Show details → visit this
        website</b> (iPhone). Everything works; the warning may come back now and then, and pisynth can't be
        installed as an app until the certificate is.</p>
    </div>

    <p>Better: pisynth uses its own certificate so the connection is private. Install it <b>once</b>; after
      that this phone opens pisynth without any warning.</p>

    <div class="card">
      <h2>1. Download the certificate</h2>
      <a class="button" href="/pisynth-ca.crt" download="pisynth-ca.crt">Download pisynth-ca.crt</a>
      <p class="muted">Check that its fingerprint starts like the one on the pisynth screen:<br>
        <code>{fingerprint}</code></p>
    </div>

    <div class="card">
      <h2>2. Install it</h2>
      <p><b>Android</b></p>
      <ol>
        <li>Settings → Security (or Security &amp; privacy) → More security settings → Encryption &amp; credentials.</li>
        <li>Install a certificate → <b>CA certificate</b> → Install anyway → pick <code>pisynth-ca.crt</code> in Downloads.</li>
      </ol>
      <p><b>iPhone / iPad</b> (open this page in Safari)</p>
      <ol>
        <li>Download, then Settings → <b>Profile Downloaded</b> → Install.</li>
        <li>Settings → General → About → <b>Certificate Trust Settings</b> → turn on <i>pisynth local CA</i>.</li>
      </ol>
      <p class="muted">This certificate can only vouch for devices on your local network (names ending in
        .local and private addresses): it can't be used for any internet site.</p>
    </div>

    <div class="card">
      <h2>3. Continue</h2>
      <button id="continue">Open pisynth</button>
    </div>
  </div>
</main>
<script src="/setup.js"></script>
</body></html>
"""

SCRIPT = """// Forward to the HTTPS app when this phone already trusts pisynth's certificate (#2427).
const port = document.body.dataset.port;
const code = location.hash;
const app = `https://${location.hostname}:${port}`;
const status = document.getElementById("status");

async function trusted() {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 4000);
  try {                                     // opaque, but it only succeeds over a trusted TLS connection
    await fetch(`${app}/build.json`, { mode: "no-cors", cache: "no-store", signal: ctl.signal });
    return true;
  } catch { return false; } finally { clearTimeout(timer); }
}

async function go(first) {
  status.textContent = "Checking the certificate…";
  if (await trusted()) {
    status.textContent = "Certificate trusted — opening pisynth…";
    location.replace(`${app}/${code}`);
    return;
  }
  status.textContent = first ? "This phone doesn't trust pisynth yet." : "Still not trusted — did step 2 finish?";
  document.getElementById("steps").hidden = false;
}

// Not trusted (yet): the app still works over HTTPS once the browser's warning is accepted.
document.getElementById("anyway").href = `${app}/${code}`;
if (!/[#&]k=/.test(code)) document.getElementById("nopair").hidden = false;
document.getElementById("continue").addEventListener("click", () => go(false));
go(true);
"""


def setup_page(fingerprint, https_port):
    return PAGE.format(fingerprint=html.escape(fingerprint or "unavailable"), port=int(https_port))
