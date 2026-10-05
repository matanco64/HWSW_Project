"""PNG frames -> GIF with one shared palette and no dithering, so pixels that
do not move stay byte-identical and gifsicle can store only what changes."""
import glob, sys
from PIL import Image, ImageChops
scene, dst, ncol = sys.argv[1], sys.argv[2], int(sys.argv[3])
paths = sorted(glob.glob(f"media/images/scenes/{scene}[0-9]*.png"))
frames = [Image.open(p).convert("RGB") for p in paths]
# Crop to the union of everything that is ever drawn, plus a margin, so the
# GIF is just the diagram and fits into the free space on a slide.
box = None
for f in frames:
    b = ImageChops.difference(f, Image.new("RGB", f.size, "white")).getbbox()
    if b:
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
m = 24
W, H = frames[0].size
box = (max(0, box[0] - m), max(0, box[1] - m), min(W, box[2] + m), min(H, box[3] + m))
frames = [f.crop(box) for f in frames]
# Move the closing pause (the finished diagram) to the front.  The first frame
# is what thumbnails, PDF export and printing show, and it would otherwise be
# the empty canvas before anything fades in; looping looks the same either way.
n_hold = 1
while n_hold < len(frames) and not ImageChops.difference(frames[-1 - n_hold], frames[-1]).getbbox():
    n_hold += 1
frames = frames[-n_hold:] + frames[:-n_hold]
w, h = frames[0].size
picks = [frames[i] for i in range(0, len(frames), max(1, len(frames) // 8))][:8]
sample = Image.new("RGB", (w, h * len(picks)))
for k, f in enumerate(picks):
    sample.paste(f, (0, h * k))
pal = sample.quantize(colors=ncol, method=Image.Quantize.MEDIANCUT)
q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
# Pillow's palette lookup is approximate and maps the white background to an
# entry like (251, 251, 251), which shows as a faint box on a white slide.
# Snap every near-white entry to pure white (same palette in every frame).
p = q[0].getpalette()
p = [255 if all(v >= 248 for v in p[i - i % 3:i - i % 3 + 3]) else c for i, c in enumerate(p)]
for f in q:
    f.putpalette(p)
durs = [60 if i % 3 == 0 else 70 for i in range(len(q))]   # averages 15 fps
q[0].save(dst, save_all=True, append_images=q[1:], duration=durs, loop=0)
print(dst, len(q), "frames, %.1f s, %dx%d" % (sum(durs) / 1000, w, h))
