// MIDI library on the Pi (#2421), phone side: the API client, folder helpers, and a small cache of
// what each file holds (duration, range, hands) worked out here the first time it is opened.
// Everything but the fetch calls is pure and unit-tested under Node.

import { songNotes, noteRange, noteTracks } from "./highway.js";
import { songFeatures, difficulty } from "./difficulty.js";

export const encodePath = p => p.split("/").map(encodeURIComponent).join("/");
export const parentOf = p => (p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");
export const baseName = p => p.slice(p.lastIndexOf("/") + 1);
export const displayName = name => baseName(name).replace(/\.midi?$/i, "").replace(/[-_]+/g, " ").trim();
// Folder label: a leading "0-", "1-"… numbers the levels and shows as "0 · homer", "1 · first steps".
export const folderLabel = name => baseName(name).replace(/^(\d+)[-_ ]+/, "$1 · ").replace(/[-_]+/g, " ").trim() || baseName(name);

// Direct children of `dir` ("" = the library root): folders first, then files, by name.
export function childrenOf(entries, dir) {
  const inside = entries.filter(e => parentOf(e.path) === dir);
  const byName = (a, b) => baseName(a.path).localeCompare(baseName(b.path), undefined, { numeric: true, sensitivity: "base" });
  return { folders: inside.filter(e => e.kind === "dir").sort(byName), files: inside.filter(e => e.kind === "file").sort(byName) };
}

// "a/b/c" → [{name:"a", path:"a"}, {name:"b", path:"a/b"}, {name:"c", path:"a/b/c"}]
export function crumbs(dir) {
  if (!dir) return [];
  const parts = dir.split("/");
  return parts.map((name, i) => ({ name, path: parts.slice(0, i + 1).join("/") }));
}

// What the modes need to know about a parsed song (#2418 viewport, hands, #2436 difficulty as written).
export function songInfo(song) {
  const notes = songNotes(song.events, song.durationMs).map((n, i) => ({ ...n, i })), r = noteRange(notes);
  return { durationMs: Math.round(song.durationMs), low: r.low, high: r.high, hands: noteTracks(notes).length, notes: notes.length,
    difficulty: difficulty(songFeatures(notes)) };
}

// Per-file info remembered in the browser, keyed by path + size (a replaced file is re-read).
// (The key's version goes up when songInfo() learns something new, so old entries are worked out again.)
export class InfoCache {
  constructor(storage = globalThis.localStorage, key = "pisynth.midiInfo.2", max = 400) {
    this.storage = storage; this.key = key; this.max = max;
    try { this.map = JSON.parse(storage?.getItem(key) || "{}"); } catch { this.map = {}; }
  }
  get(entry) { const v = this.map[entry.path]; return v && v.size === entry.size ? v.info : null; }
  set(entry, info) {
    delete this.map[entry.path];
    this.map[entry.path] = { size: entry.size, info };
    const keys = Object.keys(this.map);
    for (const k of keys.slice(0, Math.max(0, keys.length - this.max))) delete this.map[k];   // oldest first
    try { this.storage?.setItem(this.key, JSON.stringify(this.map)); } catch { /* full or private mode */ }
  }
}

async function check(res) {
  if (res.ok) return res;
  let msg = `${res.status}`;
  try { msg = (await res.json()).error || msg; } catch { /* not JSON */ }
  throw new Error(res.status === 401 ? "pair this phone again" : msg);
}

export async function listLibrary() {
  return (await (await check(await fetch("/api/midi", { credentials: "same-origin" }))).json()).entries;
}

export async function fetchFile(path) {
  return (await check(await fetch(`/api/midi/${encodePath(path)}`, { credentials: "same-origin" }))).arrayBuffer();
}

export async function uploadFile(dir, file) {
  const q = new URLSearchParams({ dir, name: file.name });
  const res = await check(await fetch(`/api/midi?${q}`, { method: "POST", body: file, credentials: "same-origin", headers: { "Content-Type": "audio/midi" } }));
  return (await res.json()).path;
}

export async function makeFolder(path) {
  await check(await fetch(`/api/midi-folders?${new URLSearchParams({ path })}`, { method: "POST", credentials: "same-origin" }));
}

export async function removeEntry(path) {
  await check(await fetch(`/api/midi/${encodePath(path)}`, { method: "DELETE", credentials: "same-origin" }));
}
