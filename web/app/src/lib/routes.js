// Companion navigation (#2419): one player screen with an "I play / Listen" toggle, and a settings
// panel behind the cog (Sound, Display, Musicians, Latency, About). Old links keep working. Pure, tested under Node.

export const PANELS = ["sound", "display", "musicians", "latency", "about"];
export const MODES = ["play", "listen"];

// Path → {mode, panel}. mode null = keep the current one (a panel opens over the player).
export function parseRoute(pathname) {
  const p = (pathname || "/").replace(/\/+$/, "") || "/";
  if (p === "/play") return { mode: "play", panel: null };
  if (p === "/listen" || p === "/demo") return { mode: "listen", panel: null };   // /demo: the old Demo tab
  const name = p.slice(1);
  if (PANELS.includes(name)) return { mode: null, panel: name };
  return { mode: null, panel: null };                                           // "/", the old Live tab, unknown
}

export function routePath({ mode, panel }) {
  if (panel) return `/${panel}`;
  return mode === "listen" ? "/listen" : "/";
}
