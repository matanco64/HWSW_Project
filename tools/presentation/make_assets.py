#!/usr/bin/env python3
"""Build presentation/assets/ from sources already in the repo.

  make_assets.py            # SVG figures -> PNG (typst), two typst-drawn diagrams -> PNG
  make_assets.py clip [--from-log]   # record `make -C hw/pyflate_accel sim` (or reuse the log) -> chain_cosim.gif

Every PNG is 1920x1080 on a white page with the figure fitted inside; nothing is redrawn,
so a slide shows exactly the figure the report shows. Needs: typst, Pillow (GIF). The clip needs the HW toolchain (source hw/env.sh).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "presentation" / "assets"

SVGS = {
    "nbody_pairs.png": "report/fig/nbody_pairs.svg",
    "pair_dependency.png": "report/fig/pair_dependency.svg",
    "print_nbody_stock.png": "report/fig/print_nbody_stock.svg",
    "print_nbody_opt.png": "report/fig/print_nbody_opt.svg",
    "grape_report.png": "report/fig/grape_report.svg",
    "grape_block_diagram.png": "hw/grape_pipeline/docs/block_diagram.svg",
    "pyflate_stages.png": "report/fig/pyflate_stages.svg",
    "huffman_tree.png": "report/fig/huffman_tree.svg",
    "print_pyflate_stock.png": "report/fig/print_pyflate_stock.svg",
    "print_pyflate_opt.png": "report/fig/print_pyflate_opt.svg",
    "decode_report.png": "report/fig/decode_report.svg",
    "huffman_block_diagram.png": "hw/huffman_engine/docs/block_diagram.svg",
    "mtf_block_diagram.png": "hw/mtf_cam/docs/block_diagram.svg",
}

# Diagrams drawn in typst (no network needed): presentation/src/<name>.typ -> assets/<name>.png
TYPST_SRC = {
    "hw_flow.png": "presentation/src/hw_flow.typ",
    "grape_uarch.png": "presentation/src/grape_uarch.typ",
}

PAGE = '#set page(width: 16in, height: 9in, margin: 0.25in, fill: white)\n' \
       '#align(center + horizon)[#image("{name}", width: 100%, height: 100%, fit: "contain")]\n'


def typst_png(svg: Path, png: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        shutil.copy(svg, d / svg.name)
        (d / "fig.typ").write_text(PAGE.format(name=svg.name), encoding="utf-8")
        subprocess.run(["typst", "compile", "--format", "png", "--ppi", "120", "fig.typ", "fig.png"],
                       cwd=d, check=True)
        shutil.copy(d / "fig.png", png)


def build_figures() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for png, rel in SVGS.items():
        typst_png(ROOT / rel, OUT / png)
        print(f"  {png:28s} <- {rel}")
    for png, rel in TYPST_SRC.items():
        subprocess.run(["typst", "compile", "--format", "png", "--ppi", "120", "--root", str(ROOT),
                        str(ROOT / rel), str(OUT / png)], check=True)
        print(f"  {png:28s} <- {rel}")


# ---- clip -------------------------------------------------------------------------------

CLIP_CMD = "make -C hw/pyflate_accel sim"
TERM_TYP = """#set page(width: 16in, height: 9in, margin: 0.4in, fill: rgb("#101418"))
#set text(font: "DejaVu Sans Mono", size: 14pt, fill: rgb("#d8dee9"))
#box(width: 100%, height: 100%, clip: true)[#raw(read("frame.txt"))]
"""
NOISE = re.compile(r"^\s*\d+\.\d+ns\s+|cocotb\.(regression|pyflate_accel)\s*")
MAX_COLS = 150
ROWS = 26


def build_clip(from_log: bool = False) -> None:
    """Run the chain co-simulation under `script` (or reuse assets/chain_cosim.log with
    --from-log), sample the output into terminal frames, render each with typst and assemble
    a GIF at 2 fps that ends on the PASS summary, capped at 25 s."""
    from PIL import Image  # noqa: WPS433

    log = OUT / "chain_cosim.log"
    if not from_log:
        env = os.environ.copy()
        shell = f"source hw/env.sh && {CLIP_CMD}"
        subprocess.run(["script", "-q", "-e", "-c", f"bash -lc '{shell}'", str(log)], cwd=ROOT, env=env)
    text = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", log.read_text(encoding="utf-8", errors="replace"))
    lines = []
    for l in text.replace("\r", "").splitlines():
        l = re.sub(r"\s+", " ", NOISE.sub("", l)).strip()
        if l:
            lines.append(l[:MAX_COLS])
    # 50 frames max: sample the log evenly, always ending on the final lines (the PASS summary).
    n_frames = min(44, max(2, len(lines) // 4))  # 43 x 0.5 s + 3 s hold = 24.5 s
    ends = [max(1, round((i + 1) * len(lines) / n_frames)) for i in range(n_frames)]
    frames = []
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "fig.typ").write_text(TERM_TYP, encoding="utf-8")
        for i, end in enumerate(ends):
            window = lines[max(0, end - ROWS):end]
            (d / "frame.txt").write_text(f"$ {CLIP_CMD}\n" + "\n".join(window), encoding="utf-8")
            subprocess.run(["typst", "compile", "--format", "png", "--ppi", "60", "fig.typ", f"f{i:03d}.png"],
                           cwd=d, check=True)
            frames.append(Image.open(d / f"f{i:03d}.png").convert("P", palette=Image.ADAPTIVE, colors=64))
        durations = [500] * len(frames)
        durations[-1] = 3000
        frames[0].save(OUT / "chain_cosim.gif", save_all=True, append_images=frames[1:],
                       duration=durations, loop=0, optimize=True)
    print(f"  chain_cosim.gif: {len(frames)} frames, log {len(lines)} lines -> {OUT / 'chain_cosim.gif'}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clip":
        build_clip(from_log="--from-log" in sys.argv)
    else:
        build_figures()
