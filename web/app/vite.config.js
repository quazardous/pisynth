// Builds the phone app into ../static — the files pisynth-web preloads and serves (#659).
// The output is committed so the Pi (and install.sh) never needs Node.
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: "../static",
    emptyOutDir: true,
    target: "es2020",
    modulePreload: { polyfill: false },   // no inline script: the server's CSP is default-src 'self'
    assetsInlineLimit: 0,                 // no data: URIs for scripts/styles either
  },
});
