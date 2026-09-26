// grape_pipeline per-step pipeline, redrawn from hw/grape_pipeline/docs/uarch.md §2 (mermaid).
// Pair i issues at cycle 2i, i = 0..9. "+n" is the dependency latency to the next stage.
#set page(width: 16in, height: 9in, margin: 0.5in, fill: white)
#set text(font: "DejaVu Sans", size: 18pt, fill: rgb("#222222"))

#let accent = rgb("#1F4E79")
#let node(title, detail, lat, w: 2.0in, fill: rgb("#f4f4f4"), stroke: rgb("#888888")) = box(width: w, height: 1.55in)[
  #place(rect(width: 100%, height: 100%, radius: 10pt, fill: fill, stroke: 1.5pt + stroke))
  #align(center + horizon)[
    #text(weight: "bold")[#title] \
    #text(size: 15pt, fill: rgb("#444444"))[#detail] \
    #text(size: 15pt, fill: accent, weight: "bold")[#lat]
  ]
]
#let arrow = box(width: 0.3in, height: 1.55in)[#align(center + horizon)[#text(size: 28pt, fill: rgb("#888888"))[→]]]

#align(center)[
  #text(size: 24pt, weight: "bold", fill: accent)[Force front end — shared units, one pair every 2 cycles (II = 2)]
  #v(0.15in)
  #stack(dir: ltr, spacing: 0pt,
    node("sub", [dx, dy, dz \ 2 × add, 2 issues], "+3"), arrow,
    node("squares + sum", [(dx² + dy²) + dz² \ 2 × mul, 2 × add], "+11"), arrow,
    node("sqrt", [SRT radix-4 \ II = 2], "+30"), arrow,
    node("d³ = dsq · s", [mul], "+3"), arrow,
    node("rcp = 1 / d³", [Newton–Raphson \ II = 2], "+22"), arrow,
    node("mag = dt · rcp", [b1m, b2m \ mul chain], "+9"), arrow,
    node("6 force terms", [dx · b2m … \ mul], "+3"),
  )
  #v(0.35in)
  #text(size: 24pt, weight: "bold", fill: accent)[Back end — strictly in pair order, then commit]
  #v(0.15in)
  #stack(dir: ltr, spacing: 0pt,
    node("ordered accumulate", [add / sub on the ADD units \ chain scoreboard], "parallel-prefix picker", w: 3.6in, fill: rgb("#dbe7f3"), stroke: accent), arrow,
    node("integrate", [mul dt · v, then add \ two roundings, as in Python], "", w: 3.6in), arrow,
    node("commit", [write body register file \ 5 bodies × (r, v)], "+2", w: 3.0in),
  )
  #v(0.3in)
  #text(size: 17pt, fill: rgb("#555555"))[
    Every operation is IEEE binary64, round-to-nearest-even, in the benchmark's own order and with no fused multiply-add,
    so the state is bit-identical to Python. Register boundaries at every "+n". Unit mix: 3 adders + 3 multipliers (uArch §7 sweep).
  ]
]
