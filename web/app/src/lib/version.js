// The companion's version (#2673): web/app/package.json's, baked in by the build, with the links to pisynth on
// GitHub. The Pi's build.json says which app it serves now: a phone still on an older cached app is told to reload.
// Pure, tested under Node.

/* global __APP_VERSION__ */
export const VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "dev";

// {version, git: {tag, ahead, commit}} from version.json, written with the build (git describe); null if unknown.
let info = null;
export const versionInfo = () => (info ??= fetch("/version.json", { cache: "no-store" }).then(r => (r.ok ? r.json() : null)).catch(() => null));

// "0.6.0" on a release; "0.6.0 + 3 changes (abc1234)" for a build made after it — what's really running.
export function versionLabel(version = VERSION, git = null) {
  if (!git || !git.ahead) return version;
  return `${git.tag} + ${git.ahead} change${git.ahead === 1 ? "" : "s"} (${git.commit})`;
}
export const commitUrl = git => (git?.commit ? `${REPO_URL}/commit/${git.commit}` : null);
export const REPO_URL = "https://github.com/quazardous/pisynth";
export const releaseUrl = v => (/^\d+\.\d+\.\d+/.test(v || "") ? `${REPO_URL}/releases/tag/v${v}` : `${REPO_URL}/releases`);

// The app on the phone vs the one pisynth serves ({version} from build.json): null when they match or nothing is known.
export function versionNotice(app, served) {
  const pi = served?.version;
  if (!pi || !app || app === "dev" || pi === app) return null;
  return `pisynth serves ${pi} — reload to update`;
}
