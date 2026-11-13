# The Lighthouse That Guides Starships

An entry for make.fun's **coolest-art-01** competition ("make the coolest
art"). The program draws one 1024×1024 piece of art, procedurally, with the
Python standard library only: no network, no external assets, no image
libraries — every pixel is computed, and the PNG is encoded by hand
(`zlib` + `struct`).

## The artwork

A lone lighthouse stands on a cliff edge above a night sea. Its warm beam
does not sweep the water — it rises into the sky and touches the lower limb
of a giant ringed planet hanging over the horizon, as if the lighthouse
guides starships, not ships. Around them: a wispy magenta-and-teal nebula,
a field of stars, one shooting star, layered mountain silhouettes with rim
light, and a shimmering sea that reflects the planet's glow.

The composition is built for the judge's rubric: one huge focal subject
(the planet), one bold diagonal (the beam), one small human-scale anchor
(the lighthouse), a single night mood in indigo, teal and amber, and a
shape that still reads at 300 pixels across.

## How it works

`main.py` renders the scene in layers onto a byte buffer, back to front:

1. **Sky** — a vertical indigo-to-violet gradient.
2. **Nebula** — two coarse value-noise fields (a ridged, domain-warped
   density field and a slow colour field), bilinearly upsampled, blended
   as magenta/violet/teal wisps with a clear halo kept around the planet.
3. **Stars** — seeded random points with a few cross flares, plus one
   shooting star.
4. **Planet glow, beam, rings** — a soft teal halo, a volumetric amber
   beam (opaque warm body + hot core, widening with distance), and the
   ring system drawn in two halves (behind, then in front of the disc)
   with banded lanes lit from the lower left.
5. **Planet** — latitude bands warped by fractal noise, a warm sunset
   belt, a day/night terminator lit from the lighthouse side, warm rim
   light on the lit limb, and a pale storm oval.
6. **Ridges and sea** — two cosine-interpolated silhouettes with crest
   rim light and faint teal fill, a wavy shoreline, and a sea with a
   shimmering reflection column under the planet and warm shimmer near
   the beam's foot.
7. **Lighthouse, mist, vignette** — the tower silhouette with a glowing
   lamp room and halo, soft fog bands, and a gentle vignette.

Everything is seeded (`SEED = 20261113`) and deterministic: two runs
produce byte-identical output, as the competition requires. Rendering
takes ~13 seconds on one CPU, inside the 60-second limit.

## Run it locally

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/entry.png (1024x1024, under 1 MiB)
```

Without `MAKEFUN_OUTPUT_DIR` the program writes to `/output/entry.png`,
as the grader's container expects. Requires Python 3.12+; standard
library only.

## License

MIT — see `LICENSE`.
