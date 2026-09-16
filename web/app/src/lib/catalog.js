// The score catalogue (#2657): thousands of public domain piano scores kept on pisynth, searched there
// (/api/catalog). A catalogue score is a song like a library file, its path "catalog:<id>". Favourites and
// recently played are per musician. Pure apart from fetch and the injected storage; tested under Node.
import { readMxl } from "./mxl.js";
import { scoreSong } from "./musicxml.js";

export const CATEGORIES = [["classical", "Classical"], ["folk", "Folk & traditional"], ["sacred", "Sacred"],
  ["children", "Children"], ["studies", "Studies"], ["dances", "Dances"]];
export const SORTS = [["popular", "Popular"], ["easy", "Easiest"], ["title", "A–Z"]];

const PREFIX = "catalog:";
export const isCatalogPath = path => typeof path === "string" && path.startsWith(PREFIX);
export const catalogPath = id => `${PREFIX}${id}`;
export const catalogId = path => (isCatalogPath(path) ? Number(path.slice(PREFIX.length)) : null);

// The search URL for a set of filters (empty ones left out).
export function catalogQuery({ q = "", category = "", composer = "", period = "", level = 0, hands = 0, sort = "popular", offset = 0, limit = 40, all = false } = {}) {
  const p = new URLSearchParams();
  if (q.trim()) p.set("q", q.trim());
  for (const [k, v] of Object.entries({ category, composer, period })) if (v) p.set(k, v);
  if (level) p.set("level", String(level));
  if (hands) p.set("hands", String(hands));
  if (sort && sort !== "popular") p.set("sort", sort);
  if (offset) p.set("offset", String(offset));
  if (limit !== 40) p.set("limit", String(limit));
  if (all) p.set("all", "1");
  const s = p.toString();
  return `/api/catalog${s ? `?${s}` : ""}`;
}

async function check(res) {
  if (res.ok) return res;
  throw new Error(res.status === 401 ? "pair this phone again" : `${res.status}`);
}

export async function searchCatalog(filters, fetcher = globalThis.fetch) {
  return (await check(await fetcher(catalogQuery(filters), { credentials: "same-origin" }))).json();
}

// A catalogue item → a playable song, from its score.
export async function loadCatalogSong(item, fetcher = globalThis.fetch) {
  const res = await check(await fetcher(`/api/catalog/${item.id}.mxl`, { credentials: "same-origin" }));
  const buf = await res.arrayBuffer(), head = new Uint8Array(buf, 0, Math.min(2, buf.byteLength));
  const xml = head[0] === 0x50 && head[1] === 0x4b ? await readMxl(buf) : new TextDecoder().decode(buf);   // PK: an .mxl zip
  const name = item.title || `Score ${item.id}`;
  return { ...scoreSong(xml, { name }), name, path: catalogPath(item.id), scoreXml: xml, credit: creditLine(item), catalog: slim(item) };
}

export const creditLine = item => [item.composer, item.licence, item.source?.replace(/^https?:\/\//, "")].filter(Boolean).join(" · ");

// What a favourite / a recent entry keeps: enough to list and open it again.
const slim = ({ id, title, composer, level, hands, seconds, licence, source }) => ({ id, title, composer, level, hands, seconds, licence, source });

// Favourites (★) and recently played, per musician: {fav: [...items], recent: [...items]}, newest first.
export class ScoreShelf {
  constructor(storage, key, maxRecent = 30) {
    this.storage = storage; this.key = key; this.maxRecent = maxRecent;
    let saved = null;
    try { saved = JSON.parse(storage?.getItem(key) || "null"); } catch { /* broken: empty */ }
    this.fav = Array.isArray(saved?.fav) ? saved.fav.filter(x => x && Number.isFinite(x.id)) : [];
    this.recent = Array.isArray(saved?.recent) ? saved.recent.filter(x => x && Number.isFinite(x.id)) : [];
  }
  save() { try { this.storage?.setItem(this.key, JSON.stringify({ fav: this.fav, recent: this.recent })); } catch { /* private mode */ } }
  isFav(id) { return this.fav.some(x => x.id === id); }
  toggleFav(item) {
    if (this.isFav(item.id)) this.fav = this.fav.filter(x => x.id !== item.id);
    else this.fav = [slim(item), ...this.fav];
    this.save();
    return this.isFav(item.id);
  }
  played(item) {
    this.recent = [slim(item), ...this.recent.filter(x => x.id !== item.id)].slice(0, this.maxRecent);
    this.save();
  }
}
