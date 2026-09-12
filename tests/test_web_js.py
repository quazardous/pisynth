"""Run the web companion's browser-side logic tests (tests/js, node:test) when Node is here —
the phone does the heavy lifting (#659), so that logic deserves tests too."""
import glob
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_logic():
    files = sorted(glob.glob(str(ROOT / "tests" / "js" / "*.test.mjs")))
    assert files
    r = subprocess.run(["node", "--test", *files], capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
