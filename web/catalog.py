"""The score catalogue (#2657): thousands of public domain piano scores to search from the companion.

Built on the PC by tools/score_catalog.py (scores/catalog.json + scores/pdmx/<id>.mxl) and copied to the Pi by
the deploy. Read once into memory — a few thousand rows — and searched there: words in any order, without
accents or case, each a prefix of a word of the title, composer, tags or period ("chop noct" finds Chopin's
nocturnes); filters by category, composer, period, level, hands; sorted by popularity, ease or title; counts
per filter value for the chips.
"""
import json
import os
import re
import threading
import unicodedata

SORTS = ("popular", "easy", "title")
PAGE_MAX = 100

# Other spellings people type (French names first): folded words added to a composer's rows.
ALIASES = {
    "Tchaikovsky": "tchaikovski tchaikowsky tschaikowsky", "Rachmaninoff": "rachmaninov rachmaninow",
    "Mussorgsky": "moussorgski mussorgski", "Rimsky-Korsakov": "rimski korsakov korsakoff", "Handel": "haendel handel",
    "Dvořák": "dvorak", "Scriabin": "scriabine skriabin", "Carolan": "o'carolan ocarolan", "Burgmüller": "burgmuller",
    "Johann Strauss II": "strauss", "J. S. Bach": "bach johann sebastian", "C. P. E. Bach": "bach carl philipp emanuel",
    "Traditional": "traditionnel trad populaire folk", "Saint-Saëns": "saint saens", "Fauré": "faure",
    "Bartók": "bartok", "Janáček": "janacek", "Albéniz": "albeniz", "Tárrega": "tarrega",
}
CATEGORY_WORDS = {"classical": "classique", "folk": "folk traditionnel", "sacred": "sacre religieux cantique",
                  "children": "enfants", "studies": "etudes exercices", "dances": "danses"}


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)).lower()).strip()


def words(s):
    return re.findall(r"[a-z0-9]+", fold(s))


class ScoreCatalog:
    def __init__(self, root):
        self.root = root
        self._lock = threading.Lock()
        self._mtime = None
        self.scores, self._words, self.by_id, self.source = [], [], {}, ""

    @property
    def path(self):
        return os.path.join(self.root, "catalog.json")

    def _load(self):
        """(Re)read catalog.json when it changed (a deploy brought a new one)."""
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            self.scores, self._words, self.by_id, self._mtime = [], [], {}, None
            return
        if mtime == self._mtime:
            return
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        scores = [s for s in data.get("scores", []) if isinstance(s, dict) and "id" in s and "file" in s]
        self._words = [frozenset(words(" ".join([s.get("title", ""), s.get("composer", ""), s.get("tags", ""),
                                                 s.get("period", ""), ALIASES.get(s.get("composer", ""), ""),
                                                 " ".join(CATEGORY_WORDS.get(c, c) for c in s.get("categories", []))])))
                       for s in scores]
        self.scores, self.by_id, self.source, self._mtime = scores, {s["id"]: s for s in scores}, data.get("source", ""), mtime

    def search(self, q="", category="", composer="", period="", level=0, hands=0, sort="popular", offset=0, limit=40,
               everything=False):
        """→ {total, items, facets, source}. `everything`: all scores, else the curated ones when the search is
        empty (a query or a filter always looks at everything)."""
        with self._lock:
            self._load()
            terms = words(q)
            narrowed = bool(terms or category or composer or period or level or hands)
            base = []
            for s, ws in zip(self.scores, self._words):
                if not (everything or narrowed or s.get("curated")):
                    continue
                if terms and not all(any(w.startswith(t) for w in ws) for t in terms):
                    continue
                base.append(s)
            facets = self._facets(base)
            rows = [s for s in base
                    if (not category or category in s.get("categories", []))
                    and (not composer or s.get("composer") == composer)
                    and (not period or s.get("period") == period)
                    and (not level or s.get("level") == level)
                    and (not hands or s.get("hands") == hands)]
            if sort == "easy":
                rows.sort(key=lambda s: (s.get("level", 5), -s.get("popularity", 0)))
            elif sort == "title":
                rows.sort(key=lambda s: fold(s.get("title", "")))
            else:
                rows.sort(key=lambda s: (not s.get("curated"), -s.get("popularity", 0)))
            offset, limit = max(0, offset), max(1, min(PAGE_MAX, limit))
            items = [{k: v for k, v in s.items() if k != "tags"} for s in rows[offset:offset + limit]]
            return {"total": len(rows), "items": items, "facets": facets, "source": self.source,
                    "size": len(self.scores)}

    @staticmethod
    def _facets(rows):
        """Counts per value, over the rows matching the words (the filters are chosen from these)."""
        out = {"categories": {}, "composers": {}, "periods": {}, "levels": {}, "hands": {}}
        for s in rows:
            for c in s.get("categories", []):
                out["categories"][c] = out["categories"].get(c, 0) + 1
            for key, field in (("composers", "composer"), ("periods", "period"), ("levels", "level"), ("hands", "hands")):
                v = s.get(field)
                if v not in (None, ""):
                    out[key][str(v)] = out[key].get(str(v), 0) + 1
        return out

    def file(self, score_id):
        """The .mxl of a catalogue score, or None."""
        with self._lock:
            self._load()
            s = self.by_id.get(score_id)
        if not s:
            return None
        path = os.path.realpath(os.path.join(self.root, s["file"]))
        if not path.startswith(os.path.realpath(self.root) + os.sep) or not os.path.isfile(path):
            return None
        return path
