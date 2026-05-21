# Bundled icon font

`pisynth-icons.ttf` is a 12-glyph subset — `settings`, `wifi`, `bluetooth`,
`bluetooth_connected`, `piano`, `volume_up`, `timer_play` (metronome), `sentiment_*` (health smiley), `pending` (font-tile loading badge) — of **Material Symbols Rounded** by Google, instanced to
`FILL=1, wght=500, GRAD=0, opsz=24` and subset with `fonttools` (the full
variable font is ~15 MB; this subset is ~3 KB). The UI draws these glyphs in the
Home top bar (ticket #306).

- Source: https://github.com/google/material-design-icons
- License: Apache License 2.0

To regenerate (e.g. to add a glyph), instance + subset the upstream variable
font with fonttools:

    fonttools varLib.instancer MaterialSymbolsRounded[...].ttf \
        FILL=1 wght=500 GRAD=0 opsz=24 -o filled.ttf
    pyftsubset filled.ttf --unicodes=e8b8,e63e,e1a7,e1a8,e521,e050,f4ba,e815,e811,e814,fffd8,ef64 \
        --no-layout-closure --output-file=pisynth-icons.ttf

Codepoints: settings e8b8 · wifi e63e · bluetooth e1a7 · bluetooth_connected e1a8 · piano e521 · volume_up e050 · timer_play (metronome) f4ba · sentiment_very_satisfied e815 · sentiment_dissatisfied e811 · sentiment_very_dissatisfied e814 · music_note_2 (synth) fffd8 · pending ef64.
