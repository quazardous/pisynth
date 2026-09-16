// Builds the phone app into ../static — the files pisynth-web preloads and serves (#659).
// The output is committed so the Pi (and install.sh) never needs Node.
//
// Dev server (#2415, `make dev`): HTTPS with the dev stack's cert (the phone's mic and service
// worker need a secure context), proxying the Pi-side API to the pisynth-web container.
import fs from "node:fs";
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { VitePWA } from "vite-plugin-pwa";

const certs = process.env.PISYNTH_DEV_CERTS;
const backend = process.env.PISYNTH_DEV_BACKEND || "https://127.0.0.1:8443";
// PISYNTH_DEV_PLAIN=1: plain HTTP (the `app-local` service, bound to the laptop's loopback).
// Chrome treats http://localhost as a secure context — Secure cookies, mic and service worker
// work — and it avoids the self-signed-cert interstitial browser automation can't click through.
const https = !process.env.PISYNTH_DEV_PLAIN && certs && fs.existsSync(`${certs}/cert.pem`)
  ? { cert: fs.readFileSync(`${certs}/cert.pem`), key: fs.readFileSync(`${certs}/key.pem`) }
  : undefined;
const api = { target: backend, secure: false, changeOrigin: false };
// The companion's version (#2673): package.json's, baked into the app and written in build.json.
const VERSION = JSON.parse(fs.readFileSync(new URL("./package.json", import.meta.url), "utf8")).version;
const define = { __APP_VERSION__: JSON.stringify(VERSION) };

// build.json: which build this is ({hash, version}) — shown in About and on the pisynth screen, and fetched by the
// setup page to test the certificate. The hash is Vite's own content hash of the app's entry chunk.
function buildInfo() {
  return {
    name: "pisynth-build-info",
    apply: "build",
    generateBundle(_, bundle) {
      const entry = Object.values(bundle).find(f => f.type === "chunk" && f.isEntry);
      const hash = entry?.fileName.match(/-([\w-]{8,})\.js$/)?.[1] ?? "dev";
      this.emitFile({ type: "asset", fileName: "build.json", source: JSON.stringify({ hash, version: VERSION }) + "\n" });
    },
  };
}

// The service worker is Workbox's (vite-plugin-pwa): it precaches this build's files with their revisions,
// replaces the old worker as soon as a new build is there (main.js then reloads the page once), and never
// caches the live parts — pairing, the API, the MIDI WebSocket, build.json.
const pwa = VitePWA({
  injectRegister: false,                  // main.js registers it (no inline script: CSP)
  registerType: "autoUpdate",
  manifest: false,                        // public/manifest.webmanifest is ours
  workbox: {
    globPatterns: ["**/*.{html,js,css,svg,png,ico,woff2,webmanifest,txt,wav}"],
    navigateFallback: "/index.html",
    navigateFallbackDenylist: [/^\/api\//, /^\/pair/, /^\/ws/, /^\/build\.json/],
    cleanupOutdatedCaches: true,
    clientsClaim: true,
    skipWaiting: true,
    inlineWorkboxRuntime: true,           // one sw.js, nothing else to serve
    sourcemap: false,
  },
});

// The GitHub Pages demo (#2669): `vite build --mode demo` → ../../dist-demo, served under /pisynth/, no Pi behind it.
// Its songs travel as static files: the starter set (library/midi, listed in demo/library.json) and the score catalogue
// subset kept in web/demo (tools/build_demo.py). No service worker there.
function demoData() {
  const repo = new URL("../../", import.meta.url).pathname;
  return {
    name: "pisynth-demo-data",
    apply: "build",
    closeBundle() {
      const out = `${repo}dist-demo/demo`;
      fs.rmSync(out, { recursive: true, force: true });
      fs.cpSync(`${repo}web/demo`, out, { recursive: true });
      fs.cpSync(`${repo}library/midi`, `${out}/library/starter`, { recursive: true, filter: p => !p.endsWith(".md") });
      const entries = [{ path: "starter", kind: "dir", origin: "sync", deletable: false }];
      const walk = rel => {
        for (const name of fs.readdirSync(`${out}/library/${rel}`).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))) {
          const r = `${rel}/${name}`, p = `${out}/library/${r}`;
          if (fs.statSync(p).isDirectory()) { entries.push({ path: r, kind: "dir", origin: "sync", deletable: false }); walk(r); }
          else if (/\.(mid|midi|musicxml|xml|mxl)$/i.test(name)) {
            entries.push({ path: r, kind: "file", type: /\.midi?$/i.test(name) ? "midi" : "score", size: fs.statSync(p).size, origin: "sync", deletable: false });
          }
        }
      };
      walk("starter");
      fs.writeFileSync(`${out}/library.json`, JSON.stringify({ entries }));
      fs.writeFileSync(`${repo}dist-demo/.nojekyll`, "");
      fs.copyFileSync(`${repo}dist-demo/index.html`, `${repo}dist-demo/404.html`);   // Pages: /pisynth/sound etc. open the app
    },
  };
}

export default defineConfig(({ mode }) => mode === "demo" ? {
  base: "/pisynth/",
  define,
  plugins: [svelte(), buildInfo(), demoData()],
  build: { outDir: "../../dist-demo", emptyOutDir: true, target: "es2020", assetsInlineLimit: 0, chunkSizeWarningLimit: 1500 },
} : {
  define,
  plugins: [svelte(), buildInfo(), pwa],
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
    chunkSizeWarningLimit: 1500,          // the score renderer (#2657) is one big chunk, loaded only when a score is shown
  },
});
