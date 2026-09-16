# The demo's data (#2669)

What the GitHub Pages demo of the web companion carries besides the app: a subset of the score catalogue.

- `catalog.json` + `catalog/<id>.mxl` — the 300 most played scores of the Pi's catalogue (small files only),
  public domain or CC0 MuseScore scores found through the PDMX dataset (Long et al., 2024, CC-BY-4.0); each
  entry names its composer, licence and source. Made by `python3 tools/build_demo.py` from `scores/`
  (see `tools/score_catalog.py`).

The demo build (`cd web/app && npx vite build --mode demo`, or the `pages` GitHub Action) copies this folder
and the starter set (`library/midi`) next to the app, and lists the starter set in `demo/library.json`.
