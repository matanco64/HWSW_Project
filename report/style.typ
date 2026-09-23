// Shared print layout. Build with the repository as Typst's root.

// pdftotext extracts every label inside an embedded vector graphic, so flame
// graphs used to dump hundreds of truncated frame names into the .txt
// deliverable. `--input txtmode=1` swaps them for a one-line pointer. Diagrams
// are not routed through this: their labels read fine as text.
#let text_edition = sys.inputs.at("txtmode", default: "0") == "1"

// The flat function tables behind every flame graph, written by
// report/summarize_profiles.py from the same SVGs and perf reports the figures
// are drawn from. Keyed by the profile's source file name.
#let profiles = json("fig/profile_functions.json")
#let profile_by_source(src) = profiles.find(p => p.source.ends-with(src))

// Text edition: the .txt is a named deliverable, so a figure must not vanish
// into a one-line pointer. The flame graph becomes its widest frames, read
// from the JSON above so the numbers cannot drift from the tables. PDF
// edition: the picture. `source:` names the profile; without it the old
// pointer line is emitted.
#let flamefig(path, source: none, top: 10, ..args) = if text_edition {
  let p = if source != none { profile_by_source(source) } else { none }
  if p == none {
    align(center, text(size: 9.5pt, style: "italic")[
      (flame graph omitted from the text companion \u{2014} see the PDF edition)
    ])
  } else {
    let rows = p.functions.slice(0, calc.min(top, p.functions.len()))
    let n = if p.total_samples == none { "perf flat report, 999 Hz" } else {
      str(p.total_samples) + " samples" }
    block(width: 100%, inset: (y: 4pt))[
      #text(size: 9.5pt)[Flame graph #raw(path) (#n), widest frames:]
      #table(columns: (2.4fr, 1fr, 1fr), align: (left, right, right),
        table.header([*Frame*], [*Inclusive*], [*Self*]),
        ..rows.map(r => ([#raw(r.name)],
          [#calc.round(r.inclusive_pct, digits: 2)%],
          [#calc.round(r.self_pct, digits: 2)%])).flatten())
    ]
  }
} else {
  image(path, ..args)
}
#let ink = rgb("#18344a")
#let pale = rgb("#eef3f7")
#let report(title, subtitle, body) = {
  set document(title: title, author: ("Matan Cohen", "Yuval Kogan"))
  set page(paper: "a4", margin: (x: 18mm, y: 17mm), numbering: "1",
    header: context if counter(page).get().first() > 1 {
      text(size: 8pt, fill: ink)[HWSW Final Project #h(1fr) #title]
    })
  set text(font: "Libertinus Serif", size: 11pt, lang: "en")
  set par(justify: false, leading: 0.55em, spacing: 0.65em)
  show heading.where(level: 1): set text(size: 14pt, fill: ink)
  show heading.where(level: 2): set text(size: 11.5pt, fill: ink)
  show raw: set text(size: 9pt)
  show link: set text(fill: rgb("#185b87"))
  set table(inset: 5pt, stroke: 0.35pt + rgb("#bdcbd5"),
    fill: (x, y) => if y == 0 { pale })
  show table: set text(size: 10pt)
  show figure.caption: set text(size: 9.5pt)
  set figure(gap: 6pt)
  // Names only. ID numbers live on their own page, report/ids.typ, exactly as
  // HW1 and HW2 did -- repeating the names under the byline said them twice in
  // one document, and this repository is public, so an ID committed once would
  // stay in its history for good.
  align(center)[
    #text(size: 21pt, weight: "bold", fill: ink)[#title] #linebreak()
    #v(3pt) #text(size: 12pt)[#subtitle] #linebreak()
    #v(4pt) #text(size: 9pt)[Matan Cohen · Yuval Kogan | Technion | HWSW Final Project] #linebreak()
    #v(5pt) #text(size: 10.5pt)[*Repository:* #link("https://github.com/matanco64/HWSW_Project")[github.com/matanco64/HWSW_Project]]
  ]
  v(9pt)
  body
}
#let note(body) = block(width: 100%, fill: pale, inset: 8pt, radius: 3pt)[#body]
#let result-table(..args) = block(breakable: false)[#table(..args)]
