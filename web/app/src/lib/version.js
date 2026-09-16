// The companion's version (#2673): web/app/package.json's, baked in by the build, with the links to pisynth on
// GitHub. The Pi's build.json says which app it serves now: a phone still on an older cached app is told to reload.
// Pure, tested under Node.

/* global __APP_VERSION__ */
export const VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "dev";
export const REPO_URL = "https://github.com/quazardous/pisynth";
export const releaseUrl = v => (/^\d+\.\d+\.\d+/.test(v || "") ? `${REPO_URL}/releases/tag/v${v}` : `${REPO_URL}/releases`);

// The app on the phone vs the one pisynth serves ({version} from build.json): null when they match or nothing is known.
export function versionNotice(app, served) {
  const pi = served?.version;
  if (!pi || !app || app === "dev" || pi === app) return null;
  return `pisynth serves ${pi} — reload to update`;
}
