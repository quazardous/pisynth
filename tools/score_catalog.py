#!/usr/bin/env python3
"""Build the score catalogue (#2657): thousands of piano scores to search from the companion, out of PDMX.

PDMX (Long et al., 2024, https://zenodo.org/records/14648209, CC-BY-4.0) indexes 250k MuseScore scores with
their licence and metadata. Kept here: piano, CC0 or Public Domain Mark, no licence conflict, deduplicated —
and only music that is really out of copyright: a composer who died before 1956 (public domain in the EU in
2026, life + 70) or a traditional / anonymous tune. A "public domain" upload of a recent song is dropped.

    python3 tools/score_catalog.py select PDMX.csv            → scores/selection.json (what to extract)
    curl -L https://zenodo.org/records/14648209/files/mxl.tar.gz?download=1 \\
      | tar -xz -C WORK --files-from scores/members.txt        (stream: only the chosen files are written)
    python3 tools/score_catalog.py build WORK                 → scores/pdmx/<id>.mxl + scores/catalog.json

scores/ is gitignored; ./deploy.sh copies it to the Pi, where pisynth-web serves it (/api/catalog).
Standard library only.
"""
import csv
import json
import math
import os
import re
import shutil
import sys
import unicodedata
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scores")
PIANO_PROGRAMS = set(range(0, 8))                  # General MIDI pianos
CURATED = 4000                                     # the most played / best rated, shown first
LICENCES = {"publicdomain": "Public Domain Mark", "cc-zero": "CC0"}

# Composers: (display name, died, period, match patterns on the accent-free, lowercase composer field).
# Only those dead before 1956. Patterns are regexes; the first composer that matches wins, so the specific
# ones (C. P. E. Bach) come before the general (Bach).
COMPOSERS = [
    ("C. P. E. Bach", 1788, "Classical", [r"\bc\.? ?p\.? ?e\.? bach", r"carl philipp emanuel"]),
    ("J. C. Bach", 1782, "Classical", [r"\bj\.? ?c\.? bach", r"johann christian bach"]),
    ("W. F. Bach", 1784, "Baroque", [r"\bw\.? ?f\.? bach", r"wilhelm friedemann"]),
    ("J. S. Bach", 1750, "Baroque", [r"\bbach\b"]),
    ("Handel", 1759, "Baroque", [r"\bh(a|ae)ndel\b"]),
    ("Vivaldi", 1741, "Baroque", [r"\bvivaldi\b"]),
    ("Telemann", 1767, "Baroque", [r"\btelemann\b"]),
    ("Scarlatti", 1757, "Baroque", [r"\bscarlatti\b"]),
    ("Purcell", 1695, "Baroque", [r"\bpurcell\b"]),
    ("Pachelbel", 1706, "Baroque", [r"\bpachelbel\b"]),
    ("Rameau", 1764, "Baroque", [r"\brameau\b"]),
    ("Couperin", 1733, "Baroque", [r"\bcouperin\b"]),
    ("Corelli", 1713, "Baroque", [r"\bcorelli\b"]),
    ("Albinoni", 1751, "Baroque", [r"\balbinoni\b"]),
    ("Buxtehude", 1707, "Baroque", [r"\bbuxtehude\b"]),
    ("Lully", 1687, "Baroque", [r"\blully\b"]),
    ("Petzold", 1733, "Baroque", [r"\bpetzold\b"]),
    ("Monteverdi", 1643, "Renaissance", [r"\bmonteverdi\b"]),
    ("Dowland", 1626, "Renaissance", [r"\bdowland\b"]),
    ("Byrd", 1623, "Renaissance", [r"\bbyrd\b"]),
    ("Palestrina", 1594, "Renaissance", [r"\bpalestrina\b"]),
    ("Tallis", 1585, "Renaissance", [r"\btallis\b"]),
    ("Susato", 1570, "Renaissance", [r"\bsusato\b"]),
    ("Mozart", 1791, "Classical", [r"\bmozart\b"]),
    ("Haydn", 1809, "Classical", [r"\bhaydn\b"]),
    ("Beethoven", 1827, "Classical", [r"\bbeethoven\b"]),
    ("Clementi", 1832, "Classical", [r"\bclementi\b"]),
    ("Diabelli", 1858, "Classical", [r"\bdiabelli\b"]),
    ("Kuhlau", 1832, "Classical", [r"\bkuhlau\b"]),
    ("Dussek", 1812, "Classical", [r"\bdussek\b"]),
    ("Gluck", 1787, "Classical", [r"\bgluck\b"]),
    ("Boccherini", 1805, "Classical", [r"\bboccherini\b"]),
    ("Salieri", 1825, "Classical", [r"\bsalieri\b"]),
    ("Hummel", 1837, "Classical", [r"\bhummel\b"]),
    ("Czerny", 1857, "Romantic", [r"\bczerny\b"]),
    ("Burgmüller", 1874, "Romantic", [r"\bburgm(u|ue)ller\b"]),
    ("Schubert", 1828, "Romantic", [r"\bschubert\b"]),
    ("Schumann", 1856, "Romantic", [r"\bschumann\b"]),
    ("Chopin", 1849, "Romantic", [r"\bchopin\b"]),
    ("Liszt", 1886, "Romantic", [r"\bliszt\b"]),
    ("Mendelssohn", 1847, "Romantic", [r"\bmendelssohn\b"]),
    ("Brahms", 1897, "Romantic", [r"\bbrahms\b"]),
    ("Tchaikovsky", 1893, "Romantic", [r"\bt(s)?chaikovsk", r"\btschaikowsk", r"\btchaikowsk"]),
    ("Grieg", 1907, "Romantic", [r"\bgrieg\b"]),
    ("Dvořák", 1904, "Romantic", [r"\bdvor(a|ak)"]),
    ("Smetana", 1884, "Romantic", [r"\bsmetana\b"]),
    ("Paganini", 1840, "Romantic", [r"\bpaganini\b"]),
    ("Rossini", 1868, "Romantic", [r"\brossini\b"]),
    ("Verdi", 1901, "Romantic", [r"\bverdi\b"]),
    ("Puccini", 1924, "Romantic", [r"\bpuccini\b"]),
    ("Bizet", 1875, "Romantic", [r"\bbizet\b"]),
    ("Gounod", 1893, "Romantic", [r"\bgounod\b"]),
    ("Offenbach", 1880, "Romantic", [r"\boffenbach\b"]),
    ("Saint-Saëns", 1921, "Romantic", [r"\bsaint[- ]sa(e|ë)ns\b"]),
    ("Fauré", 1924, "Romantic", [r"\bfaure\b"]),
    ("Franck", 1890, "Romantic", [r"\bcesar franck\b", r"\bfranck\b"]),
    ("Massenet", 1912, "Romantic", [r"\bmassenet\b"]),
    ("Wagner", 1883, "Romantic", [r"\bwagner\b"]),
    ("Weber", 1826, "Romantic", [r"\bcarl maria von weber\b", r"\bc\.? ?m\.? von weber\b"]),
    ("Field", 1837, "Romantic", [r"\bjohn field\b"]),
    ("Heller", 1888, "Romantic", [r"\bstephen heller\b"]),
    ("Gurlitt", 1901, "Romantic", [r"\bgurlitt\b"]),
    ("Streabbog", 1886, "Romantic", [r"\bstreabbog\b"]),
    ("Lemoine", 1854, "Romantic", [r"\blemoine\b"]),
    ("Duvernoy", 1880, "Romantic", [r"\bduvernoy\b"]),
    ("Hanon", 1900, "Romantic", [r"\bhanon\b"]),
    ("Köhler", 1886, "Romantic", [r"\bk(o|oe)hler\b"]),
    ("Bertini", 1876, "Romantic", [r"\bbertini\b"]),
    ("Le Couppey", 1887, "Romantic", [r"\ble couppey\b"]),
    ("Beyer", 1863, "Romantic", [r"\bferdinand beyer\b", r"\bbeyer\b"]),
    ("Lange", 1900, "Romantic", [r"\bgustav lange\b"]),
    ("Badarzewska", 1861, "Romantic", [r"\bb(a|ą)darzewska\b"]),
    ("Mussorgsky", 1881, "Romantic", [r"\bmuss?org?sk"]),
    ("Rimsky-Korsakov", 1908, "Romantic", [r"\brimsk"]),
    ("Borodin", 1887, "Romantic", [r"\bborodin\b"]),
    ("Albéniz", 1909, "Romantic", [r"\balbeniz\b"]),
    ("Granados", 1916, "Romantic", [r"\bgranados\b"]),
    ("Tárrega", 1909, "Romantic", [r"\btarrega\b"]),
    ("Sor", 1839, "Romantic", [r"\bfernando sor\b"]),
    ("Johann Strauss II", 1899, "Romantic", [r"\bstrauss\b"]),
    ("Waldteufel", 1915, "Romantic", [r"\bwaldteufel\b"]),
    ("Elgar", 1934, "Late Romantic", [r"\belgar\b"]),
    ("Mahler", 1911, "Late Romantic", [r"\bmahler\b"]),
    ("Debussy", 1918, "Modern", [r"\bdebussy\b"]),
    ("Satie", 1925, "Modern", [r"\bsatie\b"]),
    ("Ravel", 1937, "Modern", [r"\bravel\b"]),
    ("Scriabin", 1915, "Modern", [r"\bscriabin\b", r"\bskriabin\b"]),
    ("Rachmaninoff", 1943, "Modern", [r"\brach?maninov", r"\brach?maninoff"]),
    ("Joplin", 1917, "Ragtime", [r"\bjoplin\b"]),
    ("Joseph Lamb", 1960, "Ragtime", []),              # died 1960: not yet (kept out on purpose)
    ("Janáček", 1928, "Modern", [r"\bjanacek\b"]),
    ("Holst", 1934, "Modern", [r"\bholst\b"]),
    ("Gershwin", 1937, "Modern", [r"\bgershwin\b"]),
    ("Bartók", 1945, "Modern", [r"\bbartok\b"]),
    ("Chaminade", 1944, "Modern", [r"\bchaminade\b"]),
    ("MacDowell", 1908, "Romantic", [r"\bmacdowell\b"]),
    ("Sousa", 1932, "Romantic", [r"\bsousa\b"]),
    ("Foster", 1864, "Romantic", [r"\bstephen (c\.? )?foster\b"]),
    ("Carolan", 1738, "Baroque", [r"\bcarolan\b", r"o'carolan"]),
    ("Gruber", 1863, "Romantic", [r"\bgruber\b"]),
    ("Pierpont", 1893, "Romantic", [r"\bpierpont\b"]),
    ("Lowell Mason", 1872, "Romantic", [r"\blowell mason\b"]),
]
PD_YEAR = 1956
TRADITIONAL = re.compile(r"^(misc traditional|trad\b|traditional|tradicional|traditionnel|traditionell|anon\b|anonymous|anonyme|unknown|folk ?song|folksong|chanson populaire|volkslied|spiritual|negro spiritual|children'?s song|nursery rhyme)")

EXCLUDED_GENRES = {"rock", "pop", "electronic", "jazz", "rbfunksoul", "hiphop", "metal", "country", "newage",
                   "soundtrack", "reggae", "blues", "latin", "comedy", "holiday"}
CATEGORY_TAGS = {
    "sacred": re.compile(r"hymn|sacred|church|gospel|psalm|chorale|choral|christmas|noel|carol|ave maria|requiem|mass\b|liturg"
                         r"|\bjesus\b|\bchrist\b|\blord\b|\bgod\b|savio|\bsaints?\b|glory|hallelujah|alleluia|amen\b|spiritual|cantique"),
    "children": re.compile(r"child|kinder|enfant|nursery|lullaby|berceuse|comptine|kids|kid\b|album for the young|jugend"),
    "studies": re.compile(r"etude|study|studies|exercise|exercice|übung|ubung|invention|sonatina|scale|arpeggio|method|lesson|hanon|czerny|op\.? ?599|op\.? ?100\b"),
    "dances": re.compile(r"waltz|valse|walzer|minuet|menuet|menuett|mazurka|polka|polonaise|gavotte|bourr[eé]e|sarabande|gigue|jig\b|reel\b|hornpipe|tango|march|marche|marsch|ragtime|rag\b|landler|ländler|allemande|courante|ecossaise|tarantella"),
}


def fold(s):
    """Lowercase, accents off, spaces squeezed."""
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)).lower()).strip()


UNINFORMATIVE = re.compile(r"^(na|n/a|none|composer|compositor|compositeur|komponist|arranger|misc|misc tunes|various|various artists|x+|\W*)$")


def _who(f):
    for name, died, period, pats in COMPOSERS:
        if any(re.search(p, f) for p in pats):
            return name, died, period
    if TRADITIONAL.match(f):
        return "Traditional", None, "Traditional"
    return None


def composer_of(composer, artist=None, *titles):
    """(display name, died, period) of the piece, ("Traditional", None, "Traditional") for a traditional or
    anonymous tune, None when unknown (not kept). The composer and artist fields decide: the first one that says
    something names a known composer or a traditional tune, or the piece is unknown — "Composer: M. Blanter" with
    "Misc Traditional" as artist is Blanter's (died 1990), not a folk tune. Only when both say nothing can the
    title name a known composer ("Swan Lake Theme - Tchaikovsky")."""
    for raw in (composer, artist):
        f = fold(raw)
        if UNINFORMATIVE.match(f):
            continue
        return _who(f)
    for raw in titles:
        who = _who(fold(raw))
        if who and who[0] != "Traditional":
            return who
    return None


def programs(tracks):
    try:
        return [int(t) for t in (tracks or "").split("-") if t != ""]
    except ValueError:
        return None


def level_of(notes_per_bar, complexity, hands):
    """1–5, like the library's gauge: note density first, the score's complexity and two hands add."""
    npb = max(0.0, notes_per_bar)
    base = 1 if npb < 5 else 2 if npb < 9 else 3 if npb < 14 else 4 if npb < 22 else 5
    base += 1 if complexity >= 2 else 0
    base -= 1 if hands == 1 and base > 1 else 0
    return max(1, min(5, base))


def popularity(row):
    views, favs = num(row, "n_views"), num(row, "n_favorites")
    rating, ratings = num(row, "rating"), num(row, "n_ratings")
    return round(math.log10(1 + views) + 1.5 * math.log10(1 + favs) + (rating - 3) * math.log10(1 + ratings), 3)


def num(row, key):
    try:
        return float(row.get(key) or 0)
    except ValueError:
        return 0.0


def categories(genre, tags, title, composer):
    text = fold(" ".join([genre, tags, title]))
    cats = set()
    if composer in ("Traditional", "Carolan") or "folk" in genre or "worldmusic" in genre:
        cats.add("folk")
    else:
        cats.add("classical")
    if "religious" in genre:
        cats.add("sacred")
    for cat, rx in CATEGORY_TAGS.items():
        if rx.search(text):
            cats.add(cat)
    return sorted(cats)


def keep(row):
    """The catalogue entry for a PDMX row, or None."""
    if row.get("subset:no_license_conflict") != "True" or row.get("subset:deduplicated") != "True":
        return None
    if row.get("license") not in LICENCES or row.get("subset:valid_mxl_pdf") != "True":
        return None
    progs = programs(row.get("tracks"))
    if not progs or len(progs) > 2 or not set(progs) <= PIANO_PROGRAMS:
        return None
    genres = set((row.get("genres") or "NA").split("-")) - {"NA"}
    if genres & EXCLUDED_GENRES:
        return None
    who = composer_of(row.get("composer_name"), row.get("artist_name"), row.get("subtitle"), row.get("title"),
                      row.get("song_name"))                 # often only the title names the composer
    if who is None or (who[1] is not None and who[1] >= PD_YEAR):
        return None
    sid = re.search(r"(\d+)\.json$", row.get("metadata") or "")
    if not sid:
        return None
    title = (row.get("title") or row.get("song_name") or "").strip()
    title = re.sub(r"\s*[-–—]\s*" + re.escape(row.get("composer_name") or "\x00") + r"\s*$", "", title) or title
    title = re.sub(r"^traditional music\s*[-–—:]\s*", "", title, flags=re.I) or title
    npb = num(row, "notes_per_bar")
    tags = "" if row.get("tags") in (None, "NA") else row["tags"]
    genre = "-".join(sorted(genres))
    return {
        "id": int(sid.group(1)), "title": title, "composer": who[0], "period": who[2], "died": who[1],
        "genre": genre, "tags": tags, "categories": categories(genre, tags, title, who[0]),
        "bars": int(num(row, "song_length.bars")), "seconds": int(num(row, "song_length.seconds")),
        "notes": int(num(row, "n_notes")), "npb": round(npb, 1), "complexity": int(num(row, "complexity")),
        "popularity": popularity(row), "licence": LICENCES[row["license"]],
        "source": f"https://musescore.com/score/{sid.group(1)}", "member": (row.get("mxl") or "").lstrip("./"),
    }


def select(csv_path, out_dir=ROOT):
    """PDMX.csv → the chosen entries (scores/selection.json) and the archive members to extract."""
    csv.field_size_limit(10 ** 8)
    chosen = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entry = keep(row)
            if entry:
                chosen.append(entry)
    chosen.sort(key=lambda e: -e["popularity"])
    for rank, e in enumerate(chosen):
        e["curated"] = rank < CURATED
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "selection.json"), "w", encoding="utf-8") as f:
        json.dump(chosen, f, ensure_ascii=False)
    with open(os.path.join(out_dir, "members.txt"), "w", encoding="utf-8") as f:
        f.writelines(e["member"] + "\n" for e in chosen)
    return chosen


def staves_of(path):
    """How many staves the score's first part has (1 = melody, 2 = both hands), by a light read of the XML."""
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.startswith("META-INF") and n.endswith((".xml", ".musicxml"))]
        if not names:
            return 0
        with z.open(names[0]) as x:
            head = x.read(400_000).decode("utf-8", "ignore")
    m = re.search(r"<staves>\s*(\d+)\s*</staves>", head)
    parts = len(re.findall(r"<score-part\b", head))
    return int(m.group(1)) if m else min(2, max(1, parts))


def build(work_dir, out_dir=ROOT):
    """Extracted archive (WORK/mxl/…) → scores/pdmx/<id>.mxl + scores/catalog.json (what the Pi serves)."""
    with open(os.path.join(out_dir, "selection.json"), encoding="utf-8") as f:
        chosen = json.load(f)
    dest = os.path.join(out_dir, "pdmx")
    os.makedirs(dest, exist_ok=True)
    catalog, missing = [], 0
    for e in chosen:
        src = os.path.join(work_dir, e["member"])
        if not os.path.exists(src):
            missing += 1
            continue
        target = os.path.join(dest, f"{e['id']}.mxl")
        shutil.copyfile(src, target)
        try:
            hands = 2 if staves_of(target) >= 2 else 1
        except (zipfile.BadZipFile, OSError):
            os.remove(target)
            missing += 1
            continue
        item = {k: v for k, v in e.items() if k not in ("member", "npb", "complexity", "died")}
        item.update(file=f"pdmx/{e['id']}.mxl", hands=hands, level=level_of(e["npb"], e["complexity"], hands))
        catalog.append(item)
    with open(os.path.join(out_dir, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump({"source": "PDMX (Long et al., 2024) https://zenodo.org/records/14648209, CC-BY-4.0",
                   "scores": catalog}, f, ensure_ascii=False, separators=(",", ":"))
    return catalog, missing


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("select", "build"):
        sys.exit(__doc__)
    if sys.argv[1] == "select":
        chosen = select(sys.argv[2])
        print(f"{len(chosen)} scores selected ({sum(e['curated'] for e in chosen)} curated)")
    else:
        catalog, missing = build(sys.argv[2])
        print(f"{len(catalog)} scores in the catalogue, {missing} missing")
