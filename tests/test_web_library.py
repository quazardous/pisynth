"""web/library.py — the MIDI library on the Pi (#2421): what sync.sh links in, what the phone
uploads, and that no path from the network ever leaves the library."""
import os

import pytest

from web.library import FOLDER_MARK, MAX_UPLOAD, LibraryError, MidiLibrary, split_path

MIDI = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff\x2f\x00"


@pytest.fixture
def lib(tmp_path):
    root, starter, pc, outside = (tmp_path / d for d in ("home/midi", "repo/library/midi", "repo/midi", "secret"))
    for d in (root, starter / "beginner", pc / "jazz", outside):
        d.mkdir(parents=True)
    (starter / "beginner" / "minuet.mid").write_bytes(MIDI)
    (pc / "jazz" / "blues.mid").write_bytes(MIDI)
    (outside / "passwd.mid").write_bytes(MIDI)
    # what sync.sh builds: real folders, linked files
    (root / "starter" / "beginner").mkdir(parents=True)
    os.symlink(starter / "beginner" / "minuet.mid", root / "starter" / "beginner" / "minuet.mid")
    (root / "jazz").mkdir()
    os.symlink(pc / "jazz" / "blues.mid", root / "jazz" / "blues.mid")
    changed = []
    return MidiLibrary(root, {"starter": starter, "pc": pc}, on_changed=changed.append), root, outside, changed


def test_tree_lists_folders_and_files_with_their_origin(lib):
    library, root, _, _ = lib
    (root / "notes.txt").write_text("not midi")
    (root / ".hidden.mid").write_bytes(MIDI)
    t = {e["path"]: e for e in library.tree()}
    assert set(t) == {"jazz", "jazz/blues.mid", "starter", "starter/beginner", "starter/beginner/minuet.mid"}
    assert t["jazz/blues.mid"]["origin"] == "pc" and not t["jazz/blues.mid"]["deletable"]
    assert t["starter/beginner/minuet.mid"]["origin"] == "starter"
    assert t["jazz"] == {"path": "jazz", "kind": "dir", "origin": "sync", "deletable": False}
    assert library.read("jazz/blues.mid") == MIDI


def test_upload_goes_into_a_new_folder_and_never_overwrites(lib):
    library, root, _, changed = lib
    assert library.save("mine/pop", "Song.mid", MIDI) == "mine/pop/Song.mid"
    assert (root / "mine" / FOLDER_MARK).exists() and (root / "mine" / "pop" / FOLDER_MARK).exists()
    assert library.save("mine/pop", "Song.mid", MIDI) == "mine/pop/Song (2).mid"
    assert library.save("jazz", "blues.mid", MIDI) == "jazz/blues (2).mid"      # next to a PC file
    assert os.path.islink(root / "jazz" / "blues.mid")                          # the PC link untouched
    t = {e["path"]: e for e in library.tree()}
    assert t["mine/pop/Song.mid"]["origin"] == "phone" and t["mine/pop/Song.mid"]["deletable"]
    assert not any(n.endswith(".part") for n in os.listdir(root / "mine" / "pop"))
    assert changed and changed[-1] == str(root)


@pytest.mark.parametrize("folder,name,data,code", [
    ("", "x.mid", b"RIFF....", 400),                     # not MIDI
    ("", "x.txt", MIDI, 400),                            # wrong extension
    ("", "x.mid", MIDI + b"\0" * MAX_UPLOAD, 413),       # too large
    ("../secret", "x.mid", MIDI, 400),
    ("a/../..", "x.mid", MIDI, 400),
    ("", "../x.mid", MIDI, 400),
    ("", ".x.mid", MIDI, 400),
    ("a\\b", "x.mid", MIDI, 400),
])
def test_bad_uploads_are_refused(lib, folder, name, data, code):
    library, root, _, _ = lib
    with pytest.raises(LibraryError) as e:
        library.save(folder, name, data)
    assert e.value.code == code


def test_no_path_leaves_the_library(lib):
    library, root, outside, _ = lib
    os.symlink(outside, root / "escape")                                        # a link to elsewhere
    assert "escape" not in {e["path"] for e in library.tree()}
    for bad, code in (("../secret/passwd.mid", 400), ("escape/passwd.mid", 403),
                      ("jazz/../../secret/passwd.mid", 400), ("/etc/passwd.mid", 404)):   # (absolute = inside the library)
        with pytest.raises(LibraryError) as e:
            library.read(bad)
        assert e.value.code == code, bad
    with pytest.raises(LibraryError):
        library.save("escape", "x.mid", MIDI)
    assert not (outside / "x.mid").exists()


def test_delete_only_what_the_phone_added(lib):
    library, root, _, _ = lib
    path = library.save("mine", "a.mid", MIDI)
    with pytest.raises(LibraryError) as e:
        library.delete("jazz/blues.mid")
    assert e.value.code == 403                                                  # from the PC
    with pytest.raises(LibraryError) as e:
        library.delete("jazz")
    assert e.value.code == 403                                                  # a synced folder
    with pytest.raises(LibraryError) as e:
        library.delete("mine")
    assert e.value.code == 409                                                  # not empty
    library.delete(path)
    library.delete("mine")
    assert not (root / "mine").exists()
    with pytest.raises(LibraryError) as e:
        library.delete("")
    assert e.value.code == 403


def test_mkdir_and_split_path(lib):
    library, root, _, _ = lib
    assert library.mkdir("Mes morceaux/Débutant") == "Mes morceaux/Débutant"
    assert (root / "Mes morceaux" / "Débutant" / FOLDER_MARK).exists()
    with pytest.raises(LibraryError) as e:
        library.mkdir("Mes morceaux")
    assert e.value.code == 409
    assert split_path("/a/b/") == ["a", "b"] and split_path("") == []
    with pytest.raises(LibraryError):
        split_path("a//b")
