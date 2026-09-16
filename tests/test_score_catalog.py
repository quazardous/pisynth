"""The score catalogue (#2657): the PDMX selection (licence, piano, public domain composers only) and the search."""
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import score_catalog as B  # noqa: E402
from web.catalog import ScoreCatalog  # noqa: E402


def row(**kw):
    base = {"subset:no_license_conflict": "True", "subset:deduplicated": "True", "subset:valid_mxl_pdf": "True",
            "license": "cc-zero", "tracks": "0", "genres": "classical", "composer_name": "Frédéric Chopin",
            "artist_name": "NA", "subtitle": "NA", "title": "Nocturne Op. 9 No. 2", "song_name": "Nocturne",
            "metadata": "./metadata/1/123.json", "mxl": "./mxl/1/1/Qm.mxl", "n_views": "1000", "n_favorites": "10",
            "rating": "4.5", "n_ratings": "3", "song_length.bars": "34", "song_length.seconds": "240",
            "n_notes": "900", "notes_per_bar": "26", "complexity": "2", "tags": "NA"}
    base.update(kw)
    return base


def test_composers_decide_and_recent_ones_are_out():
    assert B.composer_of("J.S. Bach")[0] == "J. S. Bach"
    assert B.composer_of("Carl Philipp Emanuel Bach")[0] == "C. P. E. Bach"
    assert B.composer_of("Trad.")[0] == "Traditional"
    assert B.composer_of("NA", "Misc Traditional")[0] == "Traditional"
    # the composer field speaks first: Blanter (1990) arranged as "traditional" is not a folk tune
    assert B.composer_of("Composer: Matvei Blanter", "Misc Traditional") is None
    assert B.composer_of("NA", "NA", "Swan Lake Theme - Tchaikovsky")[0] == "Tchaikovsky"
    assert B.composer_of("NA", "NA", "Traditional air") is None     # a title alone never makes a folk tune
    assert B.composer_of("Hans Zimmer") is None


def test_keep_filters_licence_piano_genre_and_composer():
    e = B.keep(row())
    assert e["id"] == 123 and e["composer"] == "Chopin" and e["period"] == "Romantic" and e["licence"] == "CC0"
    assert e["source"] == "https://musescore.com/score/123" and "classical" in e["categories"]
    assert B.keep(row(license="cc-by")) is None
    assert B.keep(row(**{"subset:no_license_conflict": "False"})) is None
    assert B.keep(row(tracks="40")) is None                              # a violin
    assert B.keep(row(tracks="0-0-0")) is None
    assert B.keep(row(genres="soundtrack")) is None
    assert B.keep(row(composer_name="Ludovico Einaudi")) is None
    folk = B.keep(row(composer_name="Traditional", title="Traditional music - Rattle the Bottles (Reel)", genres="NA"))
    assert folk["title"] == "Rattle the Bottles (Reel)" and folk["categories"] == ["dances", "folk"]
    assert "sacred" in B.keep(row(composer_name="trad", title="Jesus Can Never Fail"))["categories"]


def test_levels():
    assert B.level_of(3, 0, 1) == 1
    assert B.level_of(12, 1, 2) == 3
    assert B.level_of(30, 3, 2) == 5
    assert B.level_of(12, 1, 1) == 2                                     # a melody alone is easier


def test_build_copies_files_and_reads_hands(tmp_path):
    work, out = tmp_path / "work", tmp_path / "out"
    (work / "mxl/1/1").mkdir(parents=True)
    with zipfile.ZipFile(work / "mxl/1/1/Qm.mxl", "w") as z:
        z.writestr("META-INF/container.xml", "<container/>")
        z.writestr("score.xml", "<score-partwise><part-list><score-part id='P1'/></part-list><part id='P1'>"
                                "<measure><attributes><staves>2</staves></attributes></measure></part></score-partwise>")
    entry = B.keep(row())
    entry["curated"] = True
    out.mkdir()
    (out / "selection.json").write_text(json.dumps([entry, {**entry, "id": 9, "member": "mxl/none.mxl"}]))
    catalog, missing = B.build(str(work), str(out))
    assert missing == 1 and len(catalog) == 1
    assert catalog[0]["hands"] == 2 and catalog[0]["level"] == 5 and (out / "pdmx/123.mxl").exists()
    assert "member" not in catalog[0]


def make_catalog(tmp_path):
    scores = [
        {"id": 1, "title": "Nocturne Op. 9 No. 2", "composer": "Chopin", "period": "Romantic", "categories": ["classical"],
         "level": 4, "hands": 2, "popularity": 9, "curated": True, "file": "pdmx/1.mxl", "tags": ""},
        {"id": 2, "title": "Swan Lake", "composer": "Tchaikovsky", "period": "Romantic", "categories": ["classical"],
         "level": 2, "hands": 2, "popularity": 12, "curated": True, "file": "pdmx/2.mxl", "tags": "ballet"},
        {"id": 3, "title": "The Kesh", "composer": "Traditional", "period": "Traditional", "categories": ["dances", "folk"],
         "level": 1, "hands": 1, "popularity": 3, "curated": False, "file": "pdmx/3.mxl", "tags": "jig"},
    ]
    (tmp_path / "pdmx").mkdir()
    for s in scores:
        (tmp_path / s["file"]).write_bytes(b"PK")
    (tmp_path / "catalog.json").write_text(json.dumps({"source": "PDMX", "scores": scores}))
    return ScoreCatalog(str(tmp_path))


def test_search_words_accents_aliases_filters_sorts(tmp_path):
    cat = make_catalog(tmp_path)
    r = cat.search()
    assert [s["id"] for s in r["items"]] == [2, 1] and r["size"] == 3        # curated first, by popularity
    assert [s["id"] for s in cat.search(everything=True)["items"]] == [2, 1, 3]
    assert [s["id"] for s in cat.search("chop noct")["items"]] == [1]
    assert [s["id"] for s in cat.search("TCHAÏKOVSKI")["items"]] == [2]      # accents, case, the French spelling
    assert [s["id"] for s in cat.search("traditionnel")["items"]] == [3]     # a query looks beyond the curated
    assert [s["id"] for s in cat.search("jig")["items"]] == [3]              # tags
    assert cat.search("danses")["total"] == 1
    assert [s["id"] for s in cat.search(category="folk")["items"]] == [3]
    assert [s["id"] for s in cat.search(level=2)["items"]] == [2]
    assert [s["id"] for s in cat.search(hands=1)["items"]] == [3]
    assert [s["id"] for s in cat.search(sort="easy", everything=True)["items"]] == [3, 2, 1]
    assert [s["id"] for s in cat.search(sort="title", everything=True)["items"]] == [1, 2, 3]
    f = cat.search(everything=True)["facets"]
    assert f["categories"] == {"classical": 2, "dances": 1, "folk": 1} and f["composers"]["Chopin"] == 1
    assert cat.search(everything=True, offset=1, limit=1)["items"][0]["id"] == 1
    assert "tags" not in cat.search()["items"][0]


def test_file_and_missing_catalogue(tmp_path):
    cat = make_catalog(tmp_path)
    assert cat.file(2).endswith("pdmx/2.mxl")
    assert cat.file(99) is None
    empty = ScoreCatalog(str(tmp_path / "nothing"))
    assert empty.search()["total"] == 0 and empty.file(1) is None
