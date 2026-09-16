// The companion's version and links (#2673).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { VERSION, REPO_URL, releaseUrl, versionNotice, versionLabel, commitUrl } from "../../web/app/src/lib/version.js";

test("version and links", () => {
  assert.equal(VERSION, "dev");                                        // not built: no version baked in
  assert.equal(REPO_URL, "https://github.com/quazardous/pisynth");
  const pkg = JSON.parse(readFileSync(new URL("../../web/app/package.json", import.meta.url), "utf8")).version;
  assert.equal(releaseUrl(pkg), `https://github.com/quazardous/pisynth/releases/tag/v${pkg}`);
  assert.equal(releaseUrl("dev"), "https://github.com/quazardous/pisynth/releases");
});

test("a build after a release says so", () => {
  assert.equal(versionLabel("0.6.0", { tag: "0.6.0", ahead: 0, commit: "494698d" }), "0.6.0");
  assert.equal(versionLabel("0.6.0", { tag: "0.6.0", ahead: 1, commit: "1d218b7" }), "0.6.0 + 1 change (1d218b7)");
  assert.equal(versionLabel("0.6.0", { tag: "0.6.0", ahead: 3, commit: "abc1234" }), "0.6.0 + 3 changes (abc1234)");
  assert.equal(versionLabel("0.6.0", null), "0.6.0");
  assert.equal(commitUrl({ commit: "abc1234" }), "https://github.com/quazardous/pisynth/commit/abc1234");
});

test("the Pi serving another version asks for a reload", () => {
  assert.equal(versionNotice("0.6.0", { version: "0.6.0", git: { tag: "0.6.0", ahead: 2, commit: "bbb" } }, { tag: "0.6.0", ahead: 1, commit: "aaa" }),
    "pisynth serves 0.6.0 + 2 changes (bbb) — reload to update");
  assert.equal(versionNotice("0.6.0", { hash: "x", version: "0.6.1" }), "pisynth serves 0.6.1 — reload to update");
  assert.equal(versionNotice("0.6.0", { version: "0.6.0" }), null);
  assert.equal(versionNotice("0.6.0", { hash: "old" }), null);           // an older build.json without a version
  assert.equal(versionNotice("dev", { version: "0.6.0" }), null);
});

test("the built app says its version in build.json", () => {
  const built = JSON.parse(readFileSync(new URL("../../web/static/build.json", import.meta.url), "utf8"));
  const pkg = JSON.parse(readFileSync(new URL("../../web/app/package.json", import.meta.url), "utf8")).version;
  assert.equal(built.version, pkg);
});
