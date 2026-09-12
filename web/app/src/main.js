import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";

if ("serviceWorker" in navigator) {
  if (import.meta.env.DEV) {
    // Dev server: no service worker — it would serve stale modules and defeat hot reload.
    navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister()));
  } else {
    // sw.js changes with every build (build hash): the new worker takes over, and the page
    // reloads once so it runs the new files — never a stale app on the phone.
    const hadController = !!navigator.serviceWorker.controller;
    navigator.serviceWorker.addEventListener("controllerchange", () => { if (hadController) location.reload(); });
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

mount(App, { target: document.getElementById("app") });
