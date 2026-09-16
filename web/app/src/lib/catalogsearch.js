// The score catalogue's search, in the browser (#2669): the GitHub Pages demo has no pisynth to ask, so it searches
// its catalogue.json here — the same rules as web/catalog.py (words in any order, accent-free prefixes of the title,
// composer, tags, period, aliases and category words; filters; sorts; counts per value). Pure, tested under Node.

export const SORTS = ["popular", "easy", "title"];
const PAGE_MAX = 100;
const ALIASES = {
  "Tchaikovsky": "tchaikovski tchaikowsky tschaikowsky", "Rachmaninoff": "rachmaninov rachmaninow",
  "Mussorgsky": "moussorgski mussorgski", "Rimsky-Korsakov": "rimski korsakov korsakoff", "Handel": "haendel handel",
  "Dvořák": "dvorak", "Scriabin": "scriabine skriabin", "Carolan": "o'carolan ocarolan", "Burgmüller": "burgmuller",
  "Johann Strauss II": "strauss", "J. S. Bach": "bach johann sebastian", "C. P. E. Bach": "bach carl philipp emanuel",
  "Traditional": "traditionnel trad populaire folk", "Saint-Saëns": "saint saens", "Fauré": "faure",
  "Bartók": "bartok", "Janáček": "janacek", "Albéniz": "albeniz", "Tárrega": "tarrega",
};
const CATEGORY_WORDS = { classical: "classique", folk: "folk traditionnel", sacred: "sacre religieux cantique",
  children: "enfants", studies: "etudes exercices", dances: "danses" };

export const fold = s => (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
const words = s => fold(s).match(/[a-z0-9]+/g) ?? [];

export class CatalogIndex {
  constructor(data) {
    this.source = data?.source ?? "";
    this.scores = (data?.scores ?? []).filter(s => s && s.id !== undefined && s.file);
    this.words = this.scores.map(s => new Set(words([s.title, s.composer, s.tags, s.period, ALIASES[s.composer] ?? "",
      (s.categories ?? []).map(c => CATEGORY_WORDS[c] ?? c).join(" ")].join(" "))));
    this.byId = new Map(this.scores.map(s => [s.id, s]));
  }

  search({ q = "", category = "", composer = "", period = "", level = 0, hands = 0, sort = "popular", offset = 0, limit = 40, all = false } = {}) {
    const terms = words(q);
    const narrowed = !!(terms.length || category || composer || period || level || hands);
    const base = [];
    this.scores.forEach((s, i) => {
      if (!(all || narrowed || s.curated)) return;
      if (terms.length && !terms.every(t => [...this.words[i]].some(w => w.startsWith(t)))) return;
      base.push(s);
    });
    const facets = { categories: {}, composers: {}, periods: {}, levels: {}, hands: {} };
    for (const s of base) {
      for (const c of s.categories ?? []) facets.categories[c] = (facets.categories[c] ?? 0) + 1;
      for (const [key, field] of [["composers", "composer"], ["periods", "period"], ["levels", "level"], ["hands", "hands"]]) {
        const v = s[field];
        if (v !== undefined && v !== null && v !== "") facets[key][String(v)] = (facets[key][String(v)] ?? 0) + 1;
      }
    }
    const rows = base.filter(s => (!category || (s.categories ?? []).includes(category)) && (!composer || s.composer === composer)
      && (!period || s.period === period) && (!level || s.level === level) && (!hands || s.hands === hands));
    if (sort === "easy") rows.sort((a, b) => (a.level ?? 5) - (b.level ?? 5) || (b.popularity ?? 0) - (a.popularity ?? 0));
    else if (sort === "title") rows.sort((a, b) => (fold(a.title) < fold(b.title) ? -1 : fold(a.title) > fold(b.title) ? 1 : 0));
    else rows.sort((a, b) => (!a.curated - !b.curated) || (b.popularity ?? 0) - (a.popularity ?? 0));
    const from = Math.max(0, offset), n = Math.max(1, Math.min(PAGE_MAX, limit));
    const items = rows.slice(from, from + n).map(({ tags, ...s }) => s);
    return { total: rows.length, items, facets, source: this.source, size: this.scores.length };
  }
}

// URL query → search options (the /api/catalog parameters).
export function searchParams(url) {
  const p = new URL(url, "http://x").searchParams, num = k => parseInt(p.get(k) ?? "0", 10) || 0;
  const sort = p.get("sort") ?? "popular";
  return { q: (p.get("q") ?? "").slice(0, 200), category: p.get("category") ?? "", composer: p.get("composer") ?? "", period: p.get("period") ?? "",
    level: num("level"), hands: num("hands"), sort: SORTS.includes(sort) ? sort : "popular", offset: num("offset"), limit: num("limit") || 40, all: p.get("all") === "1" };
}
