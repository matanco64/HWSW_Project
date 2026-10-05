# Explainer animations for the pyflate slides

Three short GIFs built with [Manim Community](https://www.manim.community/) 0.21, using the same
examples as the slides:

| GIF | Shows | Size (px) |
|---|---|---|
| `mtf.gif` | Move-to-front: decoding `2 0 0 1` with the list `[a b c d]` gives `c c c a` | 627x409 |
| `bwt.gif` | BWT: the six rotations of `banana`, sorted; the last column is `nnbaaa`, and row 3 is the original word | 860x348 |
| `inverse_bwt.gif` | Inverse BWT: start at row 3, follow `T` (2, 5, 1, 4, 0, 3), read one letter of `nnbaaa` per jump | 831x421 |

The GIFs are only the diagram: no title, subtitle or caption, because they sit on slides that already
have them (DRAFT copies of the MTF, BWT and inverse-BWT slides in the deck). Each is cropped to its
content, has a pure white background, loops, runs 11-17 s at 15 fps and is 160-290 KB. Deck colours:
navy `#1E3A5F`, accent `#E07A1F`.

Each GIF opens on the finished diagram (the closing pause is moved to the front), so a thumbnail,
a PDF export or a printout shows the complete picture rather than an empty first frame.

## Rebuild

```bash
python -m venv venv && venv/bin/pip install manim        # needs Cairo; on macOS: brew install cairo pkgconf
brew install gifsicle                                     # or your package manager

# PNG frames, not Manim's own GIF writer: Manim dithers every frame separately,
# so nothing stays still and the GIFs come out at 7-12 MB.
for s in MTF BWT InverseBWT; do
  venv/bin/manim --format png -r 1280,720 --fps 15 --disable_caching scenes.py $s
done

# One shared palette, no dithering, crop to content, near-white snapped to white,
# closing pause moved to the front; then gifsicle keeps only what changes per frame.
venv/bin/python build_gif.py MTF mtf.raw.gif 64        && gifsicle -O3 mtf.raw.gif -o mtf.gif
venv/bin/python build_gif.py BWT bwt.raw.gif 64        && gifsicle -O3 bwt.raw.gif -o bwt.gif
venv/bin/python build_gif.py InverseBWT ibwt.raw.gif 64 && gifsicle -O3 ibwt.raw.gif -o inverse_bwt.gif
```

Every `wait()` in `scenes.py` passes `frozen_frame=False`; otherwise PNG output writes a pause as a
single frame and the GIF loses its pauses. Fonts: Helvetica Neue and Menlo (Roboto, the deck font,
was not installed).
