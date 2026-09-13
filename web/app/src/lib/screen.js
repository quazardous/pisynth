// "Play mode" for the phone (#2418 / #2419): fullscreen and the screen kept awake. No orientation
// lock: the player works in portrait and in landscape, the phone turns freely. Every piece is
// optional — desktops don't need fullscreen — so each call is feature-checked and never throws.

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
  } catch { /* not allowed here: fine, the page still works */ }
}

export async function exitPlayMode() {
  await releaseAwake();
  try { if (enteredFullscreen && document.fullscreenElement) await document.exitFullscreen(); } catch { /* left already */ }
  enteredFullscreen = false;
}
