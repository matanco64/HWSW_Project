// The ten-stage hardware flow with its four human checkpoints (hw/FLOW.md).
#set page(width: 16in, height: 9in, margin: 0.5in, fill: white)
#set text(font: "DejaVu Sans", size: 22pt, fill: rgb("#222222"))

#let accent = rgb("#1F4E79")
#let cp(body) = polygon(
  fill: rgb("#dbe7f3"), stroke: 2.5pt + accent,
  (0%, 50%), (12%, 0%), (88%, 0%), (100%, 50%), (88%, 100%), (12%, 100%),
)
#let stage(name, checkpoint: false) = box(width: 2.55in, height: 1.5in)[
  #if checkpoint {
    place(cp[])
  } else {
    place(rect(width: 100%, height: 100%, radius: 10pt, fill: rgb("#f4f4f4"), stroke: 1.5pt + rgb("#888888")))
  }
  #align(center + horizon)[
    #text(weight: if checkpoint { "bold" } else { "regular" }, fill: if checkpoint { accent } else { rgb("#222222") })[#name]
    #if checkpoint [ \ #text(size: 14pt, fill: accent)[human checkpoint] ]
  ]
]
#let arrow = box(width: 0.35in, height: 1.5in)[#align(center + horizon)[#text(size: 30pt, fill: rgb("#888888"))[→]]]

#v(1.2in)
#align(center)[
  #stack(dir: ltr, spacing: 0pt,
    stage("PRD", checkpoint: true), arrow,
    stage("MAS", checkpoint: true), arrow,
    stage("uArch", checkpoint: true), arrow,
    stage("RTL"), arrow,
    stage("DV testplan"),
  )
  #v(0.9in)
  #stack(dir: ltr, spacing: 0pt,
    stage("DV bring-up"), arrow,
    stage("DV coverage"), arrow,
    stage("DV sign-off", checkpoint: true), arrow,
    stage("PPA"), arrow,
    stage("Integration"),
  )
]
#v(0.9in)
#align(center)[
  #text(size: 20pt, fill: rgb("#555555"))[
    Every stage has tool-checked exit criteria recorded with evidence. An agent pre-review runs before each
    checkpoint; a human approves it. A failed gate blocks the stage; no gate can be skipped.
  ]
]
