import { mount } from "svelte";
import "./app.css";
import App from "./App.svelte";

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

mount(App, { target: document.getElementById("app") });
