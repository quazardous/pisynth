"""midi-sync.sh (#2421): the MIDI library's links on a throwaway tree — subfolders kept, phone
uploads never replaced, stale links and the folders they leave empty pruned, phone folders kept."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "midi-sync.sh"
MIDI = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def sync(repo, lib):
    r = subprocess.run(["bash", str(SCRIPT), str(repo), str(lib)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


def put(p, data=MIDI):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_links_prunes_and_keeps_uploads(tmp_path):
    repo, lib = tmp_path / "repo", tmp_path / "home" / "midi"
    put(repo / "library/midi/beginner/minuet.mid")
    put(repo / "midi/jazz/blues.mid")
    put(repo / "midi/jazz/old/gone.MIDI")
    put(repo / "midi/README.md", b"not midi")
    put(lib / "jazz/blues.mid", b"MThd uploaded from the phone")          # same name as a PC file
    put(lib / "mine/.pisynth-folder", b"")                                 # empty phone folder

    out = sync(repo, lib)
    assert "1 starter + 1 of yours linked" in out                          # blues.mid kept as the upload
    assert os.path.islink(lib / "starter/beginner/minuet.mid")
    assert os.path.realpath(lib / "jazz/old/gone.MIDI") == str((repo / "midi/jazz/old/gone.MIDI").resolve())
    assert not os.path.islink(lib / "jazz/blues.mid")                      # the upload was not replaced
    assert not (lib / "README.md").exists()

    (repo / "midi/jazz/old/gone.MIDI").unlink()
    out = sync(repo, lib)
    assert "1 stale link(s) removed" in out
    assert not (lib / "jazz/old").exists()                                 # emptied → pruned
    assert (lib / "jazz/blues.mid").exists() and (lib / "mine/.pisynth-folder").exists()

    sync(repo, lib)                                                        # idempotent
    assert sorted(p.name for p in (lib / "starter/beginner").iterdir()) == ["minuet.mid"]
