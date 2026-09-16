// The companion's version (#2673): web/app/package.json's, baked in by the build, with the links to pisynth on
// GitHub. The Pi's build.json says which app it serves now: a phone still on an older cached app is told to reload.
// Pure, tested under Node.

/* global __APP_VERSION__, __APP_GIT__ */
export const VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "dev";
export const GIT = typeof __APP_GIT__ !== "undefined" ? __APP_GIT__ : null;     // {tag, ahead, commit} from git describe

// "0.6.0" on a release; "0.6.0 + 3 changes (abc1234)" for a build made after it — what's really running.
export function versionLabel(version = VERSION, git = GIT) {
  if (!git || !git.ahead) return version;
  return `${git.tag} + ${git.ahead} change${git.ahead === 1 ? "" : "s"} (${git.commit})`;
}
export const commitUrl = git => (git?.commit ? `${REPO_URL}/commit/${git.commit}` : null);
export const REPO_URL = "https://github.com/quazardous/pisynth";
export const releaseUrl = v => (/^\d+\.\d+\.\d+/.test(v || "") ? `${REPO_URL}/releases/tag/v${v}` : `${REPO_URL}/releases`);

// The app on the phone vs the one pisynth serves ({version} from build.json): null when they match or nothing is known.
export function versionNotice(app, served, git = GIT) {
  const pi = served?.version;
  if (!pi || !app || app === "dev") return null;
  const sameCommit = !served.git || !git || served.git.commit === git.commit;
  if (pi === app && sameCommit) return null;
  return `pisynth serves ${versionLabel(pi, served.git)} — reload to update`;
}
