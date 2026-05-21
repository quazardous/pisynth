# Sideloaded soundfonts

Drop `.sf2` / `.sf3` files here, then run `./deploy.sh`.

- `deploy.sh` rsyncs them to the Pi (`~/pisynth/soundfonts/`).
- `sync.sh` symlinks each into `~/soundfonts/`, the dir scanned by
  `start-piano.sh` — so fluidsynth loads them at startup.
- Numeric prefixes control load/boot order (`01-...`, `02-...`).

System soundfonts (MuseScore General, FluidR3 GM) are already linked into
`~/soundfonts/` by migration 002, so anything here adds to them.
