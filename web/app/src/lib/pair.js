// Pairing + the MIDI socket (#659). The QR on the pisynth screen opens /#k=<one-time token>;
// we trade it for a session cookie, then open the WebSocket (cookie-authenticated).
// The GitHub Pages demo (#2669) has no pisynth: always "paired", and a stand-in socket (lib/demobackend.js).
import { DEMO, openDemoSocket } from "./demobackend.js";

export async function ensurePaired() {
  if (DEMO) return "paired";
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
    if (s.status === 204) return "paired";
    if (s.status === 401) return "unpaired";      // only an explicit refusal means "pair again"
    return "offline";                             // 5xx / proxy error: pisynth restarting — keep the session
  } catch {
    return "offline";
  }
}

// Reconnecting WebSocket. onFrame(ArrayBuffer) for MIDI, onMessage(object) for JSON replies,
// onState("live"|"reconnecting"|"unpaired"). Returns {send(obj), close()}.
export function openMidiSocket({ onFrame, onState, onMessage = () => {} }) {
  if (DEMO) return openDemoSocket({ onFrame, onState, onMessage });
  let ws, stopped = false, delay = 500;
  const connect = () => {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);   // ws: on http://localhost (dev)
    ws.binaryType = "arraybuffer";
    ws.onopen = () => { delay = 500; onState("live"); };
    ws.onmessage = e => {
      if (e.data instanceof ArrayBuffer) onFrame(e.data);
      else { try { onMessage(JSON.parse(e.data)); } catch { /* ignore */ } }
    };
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
  return {
    send(obj) { if (ws && ws.readyState === 1) { ws.send(JSON.stringify(obj)); return true; } return false; },
    close() { stopped = true; ws && ws.close(); },
  };
}
