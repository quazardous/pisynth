// The musician playing on this phone, shared by every screen (see lib/musicians.js). Choose and rename
// under the cog → Musicians, or tap the name in the player's header.

import { loadMusicians, saveMusicians, musicianKey, cleanName } from "./musicians.js";

const loaded = loadMusicians();
export const musicians = $state({ list: loaded.list, current: loaded.current });

export const currentMusician = () => musicians.list.find(m => m.id === musicians.current) ?? musicians.list[0];

// Where a per-musician store (progress, records, infinite bests) keeps the current musician's data.
export const storeKey = base => musicianKey(base, musicians.current);

const listeners = new Set();
// Called after another musician is chosen (stores that aren't components reload their data).
export function onMusicianChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }

export function selectMusician(id) {
  if (!musicians.list.some(m => m.id === id) || musicians.current === id) return;
  musicians.current = id;
  saveMusicians(musicians);
  listeners.forEach(fn => fn(id));
}

export function renameMusician(id, name) {
  const m = musicians.list.find(x => x.id === id);
  if (!m) return;
  m.name = cleanName(name, `Musician ${musicians.list.indexOf(m) + 1}`);
  saveMusicians(musicians);
}
