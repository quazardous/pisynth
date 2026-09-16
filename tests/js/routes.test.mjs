import test from "node:test";
import assert from "node:assert/strict";
import { parseRoute, routePath } from "../../web/app/src/lib/routes.js";

test("paths map to a player mode or a settings panel; old tab links still land somewhere sensible", () => {
  assert.deepEqual(parseRoute("/"), { mode: null, panel: null });
  assert.deepEqual(parseRoute("/play"), { mode: "play", panel: null });
  assert.deepEqual(parseRoute("/listen"), { mode: "listen", panel: null });
  assert.deepEqual(parseRoute("/demo"), { mode: "listen", panel: null });        // old Demo tab
  assert.deepEqual(parseRoute("/sound"), { mode: null, panel: "sound" });
  assert.deepEqual(parseRoute("/metronome"), { mode: null, panel: "metronome" });
  assert.deepEqual(parseRoute("/latency/"), { mode: null, panel: "latency" });
  assert.deepEqual(parseRoute("/about"), { mode: null, panel: "about" });
  assert.deepEqual(parseRoute("/display"), { mode: null, panel: "display" });
  assert.deepEqual(parseRoute("/nope"), { mode: null, panel: null });
  assert.deepEqual(parseRoute(""), { mode: null, panel: null });
});

test("state → path, and back", () => {
  assert.equal(routePath({ mode: "play", panel: null }), "/");
  assert.equal(routePath({ mode: "listen", panel: null }), "/listen");
  assert.equal(routePath({ mode: "listen", panel: "sound" }), "/sound");
  for (const s of [{ mode: "listen", panel: null }, { mode: null, panel: "latency" }]) {
    const back = parseRoute(routePath(s));
    assert.equal(back.panel, s.panel);
    if (!s.panel) assert.equal(back.mode, s.mode);
  }
});
