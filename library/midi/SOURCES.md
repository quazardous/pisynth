# Starter MIDI set

A small selection shipped with pisynth so demo mode and the note highway have something to play
out of the box. `./deploy.sh` puts it in the Pi's MIDI library under `starter/` (#2421).

Every file comes from the [Mutopia Project](https://www.mutopiaproject.org/) (volunteer
LilyPond editions of public domain music) and is marked **Public Domain** there. Thanks to
Mutopia's contributors. Files are unchanged, only renamed. Each has one track per staff
(right hand / left hand).

| File | Piece | Source |
|---|---|---|
| `beginner/Bach-Minuet-A-minor-BWV-Anh-120.mid` | J. S. Bach — Minuet in A minor, BWV Anh. 120 | https://www.mutopiaproject.org/ftp/BachJS/BWVAnh120/BWV-120/BWV-120.mid |
| `beginner/Bach-Minuet-B-flat-BWV-Anh-118.mid` | J. S. Bach — Minuet in B♭ major, BWV Anh. 118 | https://www.mutopiaproject.org/ftp/BachJS/BWVAnh118/BWV-118/BWV-118.mid |
| `beginner/Clementi-Sonatina-Op36-1-mvt1.mid` | M. Clementi — Sonatina op. 36 no. 1, 1st movement | https://www.mutopiaproject.org/ftp/ClementiM/O36/sonatina-1/sonatina-1-mids.zip (`sonatina-1-1.mid`) |
| `beginner/Handel-Sonatina-Aylesford.mid` | G. F. Handel — Sonatina (Aylesford pieces) | https://www.mutopiaproject.org/ftp/HandelGF/Aylesford/20-sonatina/20-sonatina.mid |
| `beginner/Schumann-Von-fremden-Laendern-Op15-1.mid` | R. Schumann — Von fremden Ländern und Menschen, op. 15 no. 1 | https://www.mutopiaproject.org/ftp/SchumannR/O15/SchumannOp15No01/SchumannOp15No01.mid |
| `intermediate/Bach-Prelude-C-major-BWV-846.mid` | J. S. Bach — Prelude in C major, BWV 846 | https://www.mutopiaproject.org/ftp/BachJS/BWV846/wtk1-prelude1/wtk1-prelude1.mid |
| `intermediate/Beethoven-Fur-Elise-WoO-59.mid` | L. van Beethoven — Für Elise, WoO 59 | https://www.mutopiaproject.org/ftp/BeethovenLv/WoO59/fur_Elise_WoO59/fur_Elise_WoO59.mid |
| `intermediate/Chopin-Prelude-Op28-4.mid` | F. Chopin — Prelude op. 28 no. 4 | https://www.mutopiaproject.org/ftp/ChopinFF/O28/Chop-28-4/Chop-28-4.mid |
| `intermediate/Chopin-Prelude-Op28-7.mid` | F. Chopin — Prelude op. 28 no. 7 | https://www.mutopiaproject.org/ftp/ChopinFF/O28/Chop-28-7/Chop-28-7.mid |
| `intermediate/Satie-Gymnopedie-1.mid` | E. Satie — Gymnopédie no. 1 | https://www.mutopiaproject.org/ftp/SatieE/gymnopedie_1/gymnopedie_1.mid |
| `intermediate/Schumann-Traeumerei-Op15-7.mid` | R. Schumann — Träumerei, op. 15 no. 7 | https://www.mutopiaproject.org/ftp/SchumannR/O15/SchumannOp15No07/SchumannOp15No07.mid |
| `advanced/Bach-Fugue-C-major-BWV-846.mid` | J. S. Bach — Fugue in C major, BWV 846 | https://www.mutopiaproject.org/ftp/BachJS/BWV846/wtk1-fugue1/wtk1-fugue1.mid |
| `advanced/Chopin-Prelude-Op28-15.mid` | F. Chopin — Prelude op. 28 no. 15 | https://www.mutopiaproject.org/ftp/ChopinFF/O28/Chop-28-15/Chop-28-15.mid |
| `advanced/Handel-Sonatina-B-flat-HWV-585.mid` | G. F. Handel — Sonatina in B♭ major, HWV 585 | https://www.mutopiaproject.org/ftp/HandelGF/HWV585/sonatina-in-b-flat-major/sonatina-in-b-flat-major.mid |

To add your own files, don't put them here: drop them in the repo's `midi/` folder (gitignored,
subfolders kept) or upload them from the web companion.
