# Starter MIDI set

A small selection shipped with pisynth so demo mode and the note highway have something to play
out of the box. `./deploy.sh` puts it in the Pi's MIDI library under `starter/` (#2421).

The classical pieces (levels 2–4) are **Public Domain** or **CC0** scores and MIDI files.

**MIDI files** come from the [Mutopia Project](https://www.mutopiaproject.org/) (volunteer LilyPond editions of
public domain music), marked **Public Domain** there. Thanks to Mutopia's contributors. Files are unchanged,
only renamed. Each has one track per staff (right hand / left hand).

| File | Piece | Source |
|---|---|---|
| `2-beginner/Bach-Minuet-B-flat-BWV-Anh-118.mid` | J. S. Bach — Minuet in B♭ major, BWV Anh. 118 | https://www.mutopiaproject.org/ftp/BachJS/BWVAnh118/BWV-118/BWV-118.mid |
| `2-beginner/Handel-Sonatina-Aylesford.mid` | G. F. Handel — Sonatina (Aylesford pieces) | https://www.mutopiaproject.org/ftp/HandelGF/Aylesford/20-sonatina/20-sonatina.mid |
| `4-advanced/Handel-Sonatina-B-flat-HWV-585.mid` | G. F. Handel — Sonatina in B♭ major, HWV 585 | https://www.mutopiaproject.org/ftp/HandelGF/HWV585/sonatina-in-b-flat-major/sonatina-in-b-flat-major.mid |

**Scores** (#2657, MusicXML, `.mxl`) — the other pieces are played from their score. They come from
[MuseScore](https://musescore.com/) users who released them as **CC0** or **Public Domain Mark**, found through
the [PDMX dataset](https://zenodo.org/records/14648209) (Long et al., 2024, CC-BY-4.0; only scores in its
`no_license_conflict` subset). Built by `tools/starter_scores.py`: one piece cut out of a collection, two
one-staff parts merged into a grand staff, a title, and one steady tempo (the tempo of the Mutopia MIDI file
each replaces); the notes are the editors'. Thanks to them.

| File | Piece | Source (musescore.com/score/…) | Licence |
|---|---|---|---|
| `2-beginner/Bach-Minuet-A-minor-BWV-Anh-120.mxl` | J. S. Bach (attr.) — Minuet in A minor, BWV Anh. 120 | [120799](https://musescore.com/score/120799) (violin and cello, merged) | CC0 |
| `2-beginner/Clementi-Sonatina-Op36-1-mvt1.mxl` | M. Clementi — Sonatina op. 36 no. 1, 1st movement | [443356](https://musescore.com/score/443356) | CC0 |
| `2-beginner/Schumann-Von-fremden-Laendern-Op15-1.mxl` | R. Schumann — Von fremden Ländern und Menschen, op. 15 no. 1 | [4778176](https://musescore.com/score/4778176) (Kinderszenen, bars 1–23) | CC0 |
| `3-intermediate/Bach-Prelude-C-major-BWV-846.mxl` | J. S. Bach — Prelude in C major, BWV 846 | [719631](https://musescore.com/score/719631) (OpenWTC, prelude) | CC0 |
| `3-intermediate/Beethoven-Fur-Elise-WoO-59.mxl` | L. van Beethoven — Für Elise, WoO 59 | [5938638](https://musescore.com/score/5938638) | CC0 |
| `3-intermediate/Chopin-Prelude-Op28-4.mxl` | F. Chopin — Prelude op. 28 no. 4 | [6261482](https://musescore.com/score/6261482) | CC0 |
| `3-intermediate/Chopin-Prelude-Op28-7.mxl` | F. Chopin — Prelude op. 28 no. 7 | [5828624](https://musescore.com/score/5828624) (24 Preludes, no. 7) | CC0 |
| `3-intermediate/Satie-Gymnopedie-1.mxl` | E. Satie — Gymnopédie no. 1 | [5472726](https://musescore.com/score/5472726) | CC0 |
| `3-intermediate/Schumann-Traeumerei-Op15-7.mxl` | R. Schumann — Träumerei, op. 15 no. 7 | [1189536](https://musescore.com/score/1189536) (two parts, merged) | Public Domain Mark |
| `4-advanced/Bach-Fugue-C-major-BWV-846.mxl` | J. S. Bach — Fugue in C major, BWV 846 | [719631](https://musescore.com/score/719631) (OpenWTC, fugue) | CC0 |
| `4-advanced/Chopin-Prelude-Op28-15.mxl` | F. Chopin — Prelude op. 28 no. 15 | [151627](https://musescore.com/score/151627) | CC0 |

`4-advanced/Handel-Sonatina-B-flat-HWV-585.mxl` is the score of the MIDI file beside it: Mutopia's own
LilyPond source ([sonatina-in-b-flat-major.ly](https://www.mutopiaproject.org/ftp/HandelGF/HWV585/sonatina-in-b-flat-major/sonatina-in-b-flat-major.ly),
Public Domain) converted with python-ly, the same edition note for note. The other two MIDI files have no
score yet.

## Homer (`0-homer/`)

The very first notes: well-known children's songs, **whole songs**, **right hand only**, a few notes
(within G3–A4), very slow (60–72 bpm). Each song is cut into its phrases or verses, written as MIDI
markers, for the companion's hybrid mode. Same generator, same **CC0** release as below.

| File | Tune |
|---|---|
| `0-homer/1-Do-Re-Mi.mid` | three-finger exercise, C–D–E |
| `0-homer/2-Hot-cross-buns.mid` | Hot cross buns (traditional) |
| `0-homer/3-Au-clair-de-la-lune.mid` | Au clair de la lune, the four phrases (French traditional) |
| `0-homer/4-Mary-had-a-little-lamb.mid` | Mary had a little lamb (traditional) |
| `0-homer/5-Frere-Jacques.mid` | Frère Jacques (French traditional) |
| `0-homer/6-Jingle-bells.mid` | Jingle Bells, the whole chorus — J. L. Pierpont (1857) |
| `0-homer/7-Ode-to-joy.mid` | Ode to Joy, the whole theme — L. van Beethoven |

## First steps (`1-first-steps/`)

The easiest level, below beginner: well-known **public domain tunes**, whole songs, arranged for pisynth
as simply as possible — right hand on the melody, mostly in the C–G five-finger position; left hand
holding one note per bar; slow tempo; cut into parts (markers) like the homer songs. Generated by `tools/make_first_steps.py` (edit the note lists there and re-run).
These arrangements are released under **CC0**.

| File | Tune |
|---|---|
| `1-first-steps/Five-fingers-up-and-down.mid` | five-finger exercise, C to G and back |
| `1-first-steps/Au-clair-de-la-lune.mid` | Au clair de la lune (French traditional) |
| `1-first-steps/Mary-had-a-little-lamb.mid` | Mary had a little lamb (traditional) |
| `1-first-steps/Ode-to-joy.mid` | Ode to Joy — L. van Beethoven, Symphony no. 9 theme |
| `1-first-steps/Frere-Jacques.mid` | Frère Jacques (French traditional) |
| `1-first-steps/Twinkle-twinkle-little-star.mid` | Ah vous dirai-je maman / Twinkle twinkle little star |
| `1-first-steps/Jingle-bells.mid` | Jingle Bells chorus — J. L. Pierpont (1857) |

The homer and first steps songs also come with their **score** (`.musicxml` beside each `.mid`), written by
the same generator from the same notes, released under the same **CC0**.

Level folders are numbered so they list in order; the companion shows them without the number.

To add your own files, don't put them here: drop them in the repo's `midi/` folder (gitignored,
subfolders kept) or upload them from the web companion.
