// Pairing + the MIDI socket (#659). The QR on the pisynth screen opens /#k=<one-time token>;
// we trade it for a session cookie, then open the WebSocket (cookie-authenticated).

export async function ensurePaired() {
  const m = location.hash.match(/(?:^#|&)k=([\w-]+)/);
  if (m) {
    history.replaceState(null, "", location.pathname);           // never leave the token in the URL
    const r = await fetch("/pair", { method: "POST", headers: { "Content-Type": "application/json" },
                                     body: JSON.stringify({ token: m[1] }), credentials: "same-origin" });
    if (r.ok) return "paired";
    if (r.status === 403) return "expired";
  }
  try {
    const s = await fetch("/api/session", { credentials: "same-origin", cache: "no-store" });
    return s.status === 204 ? "paired" : "unpaired";
  } catch {
    return "offline";
  }
}

// Reconnecting binary WebSocket. onFrame(ArrayBuffer), onState("live"|"reconnecting"|"unpaired").
export function openMidiSocket({ onFrame, onState }) {
  let ws, stopped = false, delay = 500;
  const connect = () => {
    ws = new WebSocket(`wss://${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => { delay = 500; onState("live"); };
    ws.onmessage = e => { if (e.data instanceof ArrayBuffer) onFrame(e.data); };
    ws.onclose = async () => {
      if (stopped) return;
      const who = await ensurePaired();
      if (who === "unpaired") { onState("unpaired"); return; }
      onState("reconnecting");
      setTimeout(connect, delay);
      delay = Math.min(delay * 2, 5000);
    };
  };
  connect();
  return { close() { stopped = true; ws && ws.close(); } };
}
