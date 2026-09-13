// Several musicians on one phone: four by default ("Musician 1" … "Musician 4"), renamable, one
// selected. Each has their own level / XP, records and infinite-mode bests: those stores keep their
// data under `<key>.<musician id>`. Pure apart from the injected storage; tested under Node.
// (Kept in the browser for now; #2437 moves the musicians to the Pi.)

export const KEY = "pisynth.musicians";
export const PER_MUSICIAN = ["pisynth.progress", "pisynth.records", "pisynth.endless"];
const COUNT = 4;
const MAX_NAME = 24;

export const defaultMusicians = () =>
  Array.from({ length: COUNT }, (_, i) => ({ id: `m${i + 1}`, name: `Musician ${i + 1}` }));

export const musicianKey = (base, id) => `${base}.${id}`;

export const cleanName = (name, fallback) => (String(name ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_NAME) || fallback);

// The saved musicians, or the defaults. The first time, what this phone already had (before musicians
// existed) becomes Musician 1's.
export function loadMusicians(storage = globalThis.localStorage) {
  let saved = null;
  try { saved = JSON.parse(storage?.getItem(KEY) || "null"); } catch { /* broken: start over */ }
  const defaults = defaultMusicians();
  if (saved?.list?.length) {
    const list = defaults.map(d => ({ id: d.id, name: cleanName(saved.list.find(m => m.id === d.id)?.name, d.name) }));
    return { list, current: list.some(m => m.id === saved.current) ? saved.current : list[0].id };
  }
  for (const base of PER_MUSICIAN) {
    try {
      const old = storage?.getItem(base);
      if (old !== null && old !== undefined && storage.getItem(musicianKey(base, "m1")) === null) {
        storage.setItem(musicianKey(base, "m1"), old);
        storage.removeItem?.(base);
      }
    } catch { /* private mode */ }
  }
  const fresh = { list: defaults, current: "m1" };
  saveMusicians(fresh, storage);
  return fresh;
}

export function saveMusicians(state, storage = globalThis.localStorage) {
  try { storage?.setItem(KEY, JSON.stringify({ list: state.list, current: state.current })); } catch { /* private mode */ }
}
