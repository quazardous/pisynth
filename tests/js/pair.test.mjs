import test from "node:test";
import assert from "node:assert/strict";

// ensurePaired() only needs fetch/location/history: stub them per case.
async function withEnv({ hash = "", sessionStatus, sessionThrows = false }, fn) {
  const g = globalThis;
  g.location = { hash, pathname: "/" };
  g.history = { replaceState() {} };
  g.fetch = async (url) => {
    if (url === "/api/session") {
      if (sessionThrows) throw new TypeError("network");
      return { status: sessionStatus, ok: sessionStatus < 300 };
    }
    return { status: 403, ok: false };
  };
  const { ensurePaired } = await import("../../web/app/src/lib/pair.js");
  return fn(ensurePaired);
}

test("only a 401 means unpaired; errors and 5xx keep the session (pisynth restarting)", async () => {
  await withEnv({ sessionStatus: 204 }, async ep => assert.equal(await ep(), "paired"));
  await withEnv({ sessionStatus: 401 }, async ep => assert.equal(await ep(), "unpaired"));
  await withEnv({ sessionStatus: 502 }, async ep => assert.equal(await ep(), "offline"));
  await withEnv({ sessionThrows: true }, async ep => assert.equal(await ep(), "offline"));
  await withEnv({ hash: "#k=expired-token", sessionStatus: 401 }, async ep => assert.equal(await ep(), "expired"));
});
