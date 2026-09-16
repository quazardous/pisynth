#!/usr/bin/env python3
"""Build the classical starter scores (#2657) from their sources: cut one piece out of a collection, merge two
one-staff parts into a piano grand staff, set a title and a tempo, write a compressed .mxl.

The sources (see library/midi/SOURCES.md) are MuseScore scores from the PDMX dataset — each one CC0 or Public
Domain Mark — and Mutopia's LilyPond files converted with python-ly (`ly musicxml`). They aren't kept in the
repo (PDMX is one 1.9 GB archive); download them, then:

    python3 tools/starter_scores.py SOURCES_DIR

SOURCES_DIR holds the files named in PIECES below (musescore score id in the name). Standard library only.
"""
import copy
import io
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

LIB = os.path.join(os.path.dirname(__file__), "..", "library", "midi")

# out path (under library/midi) → source file, options. `measures`: 1-based, inclusive, in document order.
# `tempo`: quarter notes per minute, steady, the tempo of the Mutopia MIDI file it replaces.
PIECES = {
    "2-beginner/Bach-Minuet-A-minor-BWV-Anh-120.mxl": ("Bach-Anh120-120799.mxl", {"tempo": 80, "merge": True, "title": "Minuet in A minor, BWV Anh. 120", "composer": "J. S. Bach (attr.)"}),
    "2-beginner/Clementi-Sonatina-Op36-1-mvt1.mxl": ("Clementi-36-1-b-443356.mxl", {"tempo": 92, "title": "Sonatina op. 36 no. 1, 1st movement", "composer": "M. Clementi"}),
    "2-beginner/Schumann-Von-fremden-Laendern-Op15-1.mxl": ("Schumann-Kinderszenen-4778176.mxl", {"tempo": 72, "measures": (1, 23), "title": "Von fremden Ländern und Menschen, op. 15 no. 1", "composer": "R. Schumann"}),
    "3-intermediate/Bach-Prelude-C-major-BWV-846.mxl": ("OpenWTC-PF1-719631.mxl", {"tempo": 60, "measures": (1, 35), "title": "Prelude in C major, BWV 846", "composer": "J. S. Bach"}),
    "3-intermediate/Beethoven-Fur-Elise-WoO-59.mxl": ("FurElise-b-5938638.mxl", {"tempo": 72, "title": "Für Elise, WoO 59", "composer": "L. van Beethoven"}),
    "3-intermediate/Chopin-Prelude-Op28-4.mxl": ("Chopin-28-4-6261482.mxl", {"tempo": 56, "title": "Prelude op. 28 no. 4", "composer": "F. Chopin"}),
    "3-intermediate/Chopin-Prelude-Op28-7.mxl": ("Chopin-28-all-5828624.mxl", {"tempo": 120, "measures": (182, 198), "title": "Prelude op. 28 no. 7", "composer": "F. Chopin"}),
    "3-intermediate/Satie-Gymnopedie-1.mxl": ("Gymno-b-5472726.mxl", {"tempo": 66, "title": "Gymnopédie no. 1", "composer": "E. Satie"}),
    "3-intermediate/Schumann-Traeumerei-Op15-7.mxl": ("Traumerei-1189536.mxl", {"tempo": 60, "merge": True, "title": "Träumerei, op. 15 no. 7", "composer": "R. Schumann"}),
    "4-advanced/Bach-Fugue-C-major-BWV-846.mxl": ("OpenWTC-PF1-719631.mxl", {"tempo": 66, "measures": (36, 62), "title": "Fugue in C major, BWV 846", "composer": "J. S. Bach"}),
    "4-advanced/Chopin-Prelude-Op28-15.mxl": ("Chopin-28-15-151627.mxl", {"tempo": 80, "title": "Prelude op. 28 no. 15", "composer": "F. Chopin"}),
    # beside its Mutopia MIDI file: the same edition, converted from its LilyPond source (the others' conversions
    # come out broken: BWV Anh. 118's left hand slips, several are empty)
    "4-advanced/Handel-Sonatina-B-flat-HWV-585.mxl": ("sonatina-in-b-flat-major.musicxml", {"tempo": 120, "title": "Sonatina in B♭ major, HWV 585", "composer": "G. F. Handel"}),
}


def load(path):
    if path.endswith(".mxl"):
        z = zipfile.ZipFile(path)
        container = ET.fromstring(z.read("META-INF/container.xml"))
        root = next(e for e in container.iter() if e.tag.endswith("rootfile")).get("full-path")
        return ET.fromstring(z.read(root))
    return ET.parse(path).getroot()


def _attr_state(measures):
    """The attributes in force after these measures: divisions, key, time, staves, clefs (by number)."""
    state, clefs = {}, {}
    for m in measures:
        for a in m.findall("attributes"):
            for child in a:
                if child.tag == "clef":
                    clefs[child.get("number", "1")] = child
                elif child.tag in ("divisions", "key", "time", "staves"):
                    state[child.tag] = child
    return state, clefs


def _last_tempo(measures):
    tempo = None
    for m in measures:
        for s in m.iter("sound"):
            if s.get("tempo"):
                tempo = s.get("tempo")
    return tempo


def cut(root, first, last):
    """Keep measures first..last (1-based, document order) of every part, with the attributes and tempo in force."""
    for part in root.findall("part"):
        ms = part.findall("measure")
        before, keep = ms[:first - 1], ms[first - 1:last]
        state, clefs = _attr_state(before)
        tempo = _last_tempo(before)
        for m in ms:
            part.remove(m)
        head = keep[0]
        attrs = head.find("attributes")
        if attrs is None:
            attrs = ET.Element("attributes")
            head.insert(0, attrs)
        have = {c.tag for c in attrs} | {"clef:" + c.get("number", "1") for c in attrs.findall("clef")}
        order = ["divisions", "key", "time", "staves"]
        for pos, tag in enumerate(order):
            if tag not in have and tag in state:
                attrs.insert(pos, copy.deepcopy(state[tag]))
        for num, clef in clefs.items():
            if "clef:" + num not in have:
                attrs.append(copy.deepcopy(clef))
        if tempo and not any(s.get("tempo") for s in head.iter("sound")):
            head.insert(1, _tempo_direction(tempo))
        for pr in head.findall("print"):
            pr.attrib.pop("new-page", None)
            pr.attrib.pop("new-system", None)
        for m in keep:
            part.append(m)
    renumber(root)


def renumber(root):
    for part in root.findall("part"):
        ms = part.findall("measure")
        start = 0 if ms and ms[0].get("implicit") == "yes" else 1
        for k, m in enumerate(ms):
            m.set("number", str(start + k))


def _tempo_direction(bpm):
    d = ET.Element("direction", placement="above")
    dt = ET.SubElement(d, "direction-type")
    ET.SubElement(dt, "metronome").extend([_el("beat-unit", "quarter"), _el("per-minute", str(bpm))])
    ET.SubElement(d, "sound", tempo=str(bpm))
    return d


def _el(tag, text):
    e = ET.Element(tag)
    e.text = text
    return e


def _measure_len(m):
    pos = top = 0
    for e in m:
        if e.tag in ("note", "forward"):
            if e.tag == "note" and e.find("chord") is not None:
                continue
            pos += int(e.findtext("duration") or 0)
        elif e.tag == "backup":
            pos -= int(e.findtext("duration") or 0)
        top = max(top, pos)
    return top


def merge(root):
    """Two one-staff parts (upper, lower) → one piano part on two staves."""
    parts = root.findall("part")
    if len(parts) != 2:
        raise ValueError("merge wants exactly two parts")
    upper, lower = parts
    div_u = int(_attr_state(upper.findall("measure"))[0]["divisions"].text)
    div_l = int(_attr_state(lower.findall("measure"))[0]["divisions"].text)
    if div_u != div_l:
        raise ValueError(f"divisions differ ({div_u} vs {div_l})")
    for clef in upper.iter("clef"):                                # the upper part's clefs are staff 1's
        clef.set("number", "1")
    for mu, ml in zip(upper.findall("measure"), lower.findall("measure")):
        length = _measure_len(mu)
        au = mu.find("attributes")
        for a in ml.findall("attributes"):                        # the lower staff's clef/key/time changes
            for child in list(a):
                if child.tag == "clef":
                    child.set("number", "2")
                    if au is None:
                        au = ET.Element("attributes")
                        mu.insert(0, au)
                    au.append(child)
            ml.remove(a)
        backup = ET.Element("backup")
        ET.SubElement(backup, "duration").text = str(length)
        mu.append(backup)
        for e in list(ml):
            if e.tag in ("note", "direction", "forward", "backup", "harmony"):
                if e.tag in ("note", "direction", "forward"):
                    staff = e.find("staff")
                    if staff is None:
                        staff = ET.SubElement(e, "staff")
                        if e.tag == "note":                        # <staff> goes after voice/type/dot/accidental…: before notations/lyric
                            e.remove(staff)
                            idx = next((i for i, c in enumerate(e) if c.tag in ("beam", "notations", "lyric", "play")), len(e))
                            e.insert(idx, staff)
                    staff.text = "2"
                    voice = e.find("voice")
                    if voice is not None:
                        voice.text = str(int(voice.text or 1) + 4)
                mu.append(e)
            elif e.tag == "barline" and mu.find("barline[@location='%s']" % e.get("location", "right")) is None:
                mu.append(e)
    root.remove(lower)
    pl = root.find("part-list")
    for sp in pl.findall("score-part"):
        if sp.get("id") == lower.get("id"):
            pl.remove(sp)
        else:
            name = sp.find("part-name")
            if name is not None:
                name.text = "Piano"
    head = upper.find("measure")
    au = head.find("attributes")
    if au.find("staves") is None:
        idx = [c.tag for c in au].index("clef") if au.find("clef") is not None else len(au)
        au.insert(idx, _el("staves", "2"))
    if not any(c.get("number") == "2" for c in au.findall("clef")):
        bass = ET.SubElement(au, "clef", number="2")
        bass.extend([_el("sign", "F"), _el("line", "4")])


def set_tempo(root, bpm):
    """One steady tempo, `bpm`, from the start: a learner's tempo. The editions' tempo maps (a performance's
    rubato, a metronome mark on every bar) go; written words (rit., a tempo…) stay."""
    for parent in root.iter():
        for d in [c for c in parent if c.tag == "direction"]:
            for dt in d.findall("direction-type"):
                if dt.find("metronome") is not None:
                    d.remove(dt)
            for snd in d.findall("sound"):
                snd.attrib.pop("tempo", None)
                if not snd.attrib and not len(snd):
                    d.remove(snd)
            if d.find("direction-type") is None and d.find("sound") is None:
                parent.remove(d)
    for snd in root.iter("sound"):
        snd.attrib.pop("tempo", None)
    head = root.find("part").find("measure")
    kids = [c.tag for c in head]
    idx = kids.index("attributes") + 1 if "attributes" in kids else 0
    head.insert(idx, _tempo_direction(bpm))


def set_title(root, title, composer):
    for c in root.findall("credit"):
        root.remove(c)
    for tag in ("work", "movement-number", "movement-title"):
        for e in root.findall(tag):
            root.remove(e)
    work = ET.Element("work")
    ET.SubElement(work, "work-title").text = title
    root.insert(0, work)
    ident = root.find("identification")
    if ident is None:
        ident = ET.Element("identification")
        root.insert(1, ident)
    for c in ident.findall("creator"):
        ident.remove(c)
    creator = ET.Element("creator", type="composer")
    creator.text = composer
    ident.insert(0, creator)


def write_mxl(root, path):
    body = io.BytesIO()
    body.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
    body.write(b'<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">\n')
    ET.ElementTree(root).write(body, encoding="utf-8", xml_declaration=False)
    name = os.path.splitext(os.path.basename(path))[0] + ".musicxml"
    container = (f'<?xml version="1.0" encoding="UTF-8"?>\n<container><rootfiles><rootfile full-path="{name}" '
                 'media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>\n')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.recordare.musicxml")
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(name, body.getvalue(), compress_type=zipfile.ZIP_DEFLATED)


def build(src_dir, out_dir=LIB, only=None):
    for out, (src, opt) in PIECES.items():
        if only and out not in only:
            continue
        root = load(os.path.join(src_dir, src))
        if "measures" in opt:
            cut(root, *opt["measures"])
        if opt.get("merge"):
            merge(root)
        if "tempo" in opt:
            set_tempo(root, opt["tempo"])
        set_title(root, opt["title"], opt["composer"])
        renumber(root)
        dest = os.path.join(out_dir, out)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        write_mxl(root, dest)
        print(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    build(sys.argv[1], *(sys.argv[2:3] or []))
