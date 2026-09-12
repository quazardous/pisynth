import struct

from pisynth.core.soundfonts import font_label, read_sf_presets, sf_key


def _chunk(cid, data):
    return cid + struct.pack("<I", len(data)) + data + (b"\0" if len(data) & 1 else b"")


def _phdr_record(name, prog, bank):
    return name.encode().ljust(20, b"\0") + struct.pack("<HHHIII", prog, bank, 0, 0, 0, 0)


def _write_sf2(path, presets):
    phdr = b"".join(_phdr_record(n, p, b) for n, p, b in presets) + _phdr_record("EOP", 0, 0)
    pdta = b"pdta" + _chunk(b"pbag", b"\0" * 4) + _chunk(b"phdr", phdr)
    body = b"sfbk" + _chunk(b"LIST", b"INFO" + _chunk(b"ifil", b"\2\0\1\0")) + _chunk(b"LIST", pdta)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def test_reads_presets_from_phdr_sorted_without_eop(tmp_path):
    sf = tmp_path / "01-Test_Font.sf2"
    _write_sf2(sf, [("Rhodes", 4, 0), ("Grand Piano", 0, 0), ("Standard", 0, 128)])
    assert read_sf_presets(str(sf)) == [(0, 0, "Grand Piano"), (0, 4, "Rhodes"), (128, 0, "Standard")]


def test_not_a_soundfont_gives_no_presets(tmp_path):
    bad = tmp_path / "x.sf2"
    bad.write_bytes(b"RIFF\0\0\0\0WAVEfmt ")
    assert read_sf_presets(str(bad)) == []
    assert read_sf_presets(str(tmp_path / "missing.sf2")) == []


def test_labels_and_keys():
    assert font_label("/sf/01-MuseScore_General.sf3") == "MuseScore General"
    assert font_label("Nice-Steinway-Lite.SF2") == "Nice Steinway Lite"
    assert sf_key("/home/pi/soundfonts/02-FluidR3_GM.sf2") == "02-FluidR3_GM.sf2"
    assert sf_key(None) == ""
