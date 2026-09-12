// Builds the phone app into ../static — the files pisynth-web preloads and serves (#659).
// The output is committed so the Pi (and install.sh) never needs Node.
//
// Dev server (#2415, `make dev`): HTTPS with the dev stack's cert (the phone's mic and service
// worker need a secure context), proxying the Pi-side API to the pisynth-web container.
import crypto from "node:crypto";
import fs from "node:fs";
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

const certs = process.env.PISYNTH_DEV_CERTS;
const backend = process.env.PISYNTH_DEV_BACKEND || "https://127.0.0.1:8443";
// PISYNTH_DEV_PLAIN=1: plain HTTP (the `app-local` service, bound to the laptop's loopback).
// Chrome treats http://localhost as a secure context — Secure cookies, mic and service worker
// work — and it avoids the self-signed-cert interstitial browser automation can't click through.
const https = !process.env.PISYNTH_DEV_PLAIN && certs && fs.existsSync(`${certs}/cert.pem`)
  ? { cert: fs.readFileSync(`${certs}/cert.pem`), key: fs.readFileSync(`${certs}/key.pem`) }
  : undefined;
const api = { target: backend, secure: false, changeOrigin: false };

// Emits sw.js with the build hash + the exact precache list (see src/sw.template.js).
function serviceWorker() {
  return {
    name: "pisynth-service-worker",
    apply: "build",
    enforce: "post",
    generateBundle(_, bundle) {
      const files = Object.keys(bundle).filter(f => !f.endsWith(".map")).sort();
      const h = crypto.createHash("sha256");
      for (const f of files) {
        const out = bundle[f];
        h.update(f);
        h.update(out.type === "chunk" ? out.code : out.source);
      }
      for (const f of fs.readdirSync("public").sort()) {         // manifest, icon: part of the app too
        h.update(f);
        h.update(fs.readFileSync(`public/${f}`));
      }
      const hash = h.digest("hex").slice(0, 12);
      const precache = ["/", ...files.filter(f => f !== "index.html").map(f => `/${f}`),
                        ...fs.readdirSync("public").sort().map(f => `/${f}`)];
      const source = fs.readFileSync("src/sw.template.js", "utf8")
        .replaceAll("__BUILD_HASH__", hash).replaceAll("__PRECACHE__", JSON.stringify(precache));
      this.emitFile({ type: "asset", fileName: "sw.js", source });
      this.emitFile({ type: "asset", fileName: "build.json", source: JSON.stringify({ hash }) + "\n" });
    },
  };
}

export default defineConfig({
  plugins: [svelte(), serviceWorker()],
  server: {
    https,
    port: 5173,
    strictPort: true,
    proxy: { "/pair": api, "/api": api, "/ws": { ...api, ws: true } },
  },
  build: {
    outDir: "../static",
    emptyOutDir: true,
    target: "es2020",
    modulePreload: { polyfill: false },   // no inline script: the server's CSP is default-src 'self'
    assetsInlineLimit: 0,                 // no data: URIs for scripts/styles either
  },
});
