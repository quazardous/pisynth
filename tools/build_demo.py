#!/usr/bin/env python3
"""The GitHub Pages demo's score catalogue (#2669): a subset of the Pi's catalogue, kept in the repo (web/demo).

The full catalogue (scores/, built by tools/score_catalog.py) is too big for the demo and isn't in git; the demo
carries the most played scores of it, so the gallery has something to search:

    python3 tools/build_demo.py [COUNT]          # default 300 → web/demo/catalog.json + web/demo/catalog/<id>.mxl

The demo build itself (`cd web/app && npx vite build --mode demo`) copies web/demo and the starter set next to the
app. Standard library only.
"""
import json
import os
import shutil
import sys

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCORES = os.path.join(REPO, "scores")
DEMO = os.path.join(REPO, "web", "demo")


def build(count=300, scores=SCORES, demo=DEMO, max_bytes=30_000):
    """The `count` most played scores whose file is at most `max_bytes` (the demo stays light: ~6 MB)."""
    with open(os.path.join(scores, "catalog.json"), encoding="utf-8") as f:
        data = json.load(f)
    ranked = sorted(data["scores"], key=lambda s: (not s.get("curated"), -s.get("popularity", 0)))
    chosen = []
    out = os.path.join(demo, "catalog")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    for s in ranked:
        if len(chosen) >= count:
            break
        src = os.path.join(scores, s["file"])
        if not os.path.isfile(src) or os.path.getsize(src) > max_bytes:
            continue
        shutil.copyfile(src, os.path.join(out, f"{s['id']}.mxl"))
        chosen.append({**s, "file": f"catalog/{s['id']}.mxl", "curated": True})
    with open(os.path.join(demo, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump({"source": data.get("source", ""), "scores": chosen}, f, ensure_ascii=False, separators=(",", ":"))
    return chosen


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    chosen = build(n)
    size = sum(os.path.getsize(os.path.join(DEMO, s["file"])) for s in chosen)
    print(f"{len(chosen)} scores in the demo catalogue, {size / 1e6:.1f} MB")
