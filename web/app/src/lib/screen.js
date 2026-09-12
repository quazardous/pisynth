// "Play mode" for the phone (#2418 / #2419): fullscreen, portrait lock, screen kept awake.
// Every piece is optional — iOS Safari has no orientation lock, desktops don't need fullscreen —
// so each call is feature-checked and never throws.

let wakeLock = null, wantAwake = false, enteredFullscreen = false;

const onVisible = async () => {
  if (wantAwake && document.visibilityState === "visible" && !wakeLock) await keepAwake();
};

async function keepAwake() {
  wantAwake = true;
  try {
    if (!("wakeLock" in navigator) || wakeLock) return;
    wakeLock = await navigator.wakeLock.request("screen");
    wakeLock.addEventListener?.("release", () => { wakeLock = null; });
    document.addEventListener("visibilitychange", onVisible);   // the lock drops when the tab hides
  } catch { wakeLock = null; }
}

export async function releaseAwake() {
  wantAwake = false;
  document.removeEventListener("visibilitychange", onVisible);
  try { await wakeLock?.release(); } catch { /* already gone */ }
  wakeLock = null;
}

// Touch screens only: on a laptop fullscreen would just be in the way.
export const isTouch = () => globalThis.matchMedia?.("(pointer: coarse)").matches ?? false;

// Call from a tap (fullscreen needs a user gesture).
export async function enterPlayMode({ fullscreen = isTouch() } = {}) {
  await keepAwake();
  if (!fullscreen) return;
  try {
    const el = document.documentElement;
    if (!document.fullscreenElement && el.requestFullscreen) {
      await el.requestFullscreen({ navigationUI: "hide" });
      enteredFullscreen = true;
    }
    await screen.orientation?.lock?.("portrait");
  } catch { /* not allowed here: the layout adapts anyway */ }
}

export async function exitPlayMode() {
  await releaseAwake();
  try { screen.orientation?.unlock?.(); } catch { /* nothing locked */ }
  try { if (enteredFullscreen && document.fullscreenElement) await document.exitFullscreen(); } catch { /* left already */ }
  enteredFullscreen = false;
}
