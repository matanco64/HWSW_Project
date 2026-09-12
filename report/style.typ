// Shared print layout. Build with the repository as Typst's root.

// The .txt deliverables are pdftotext exports of the compiled PDF, and
// pdftotext extracts every text label inside an embedded vector graphic. For
// the annotated flame graphs that is several hundred truncated frame names
// apiece, dumped into the middle of the prose: they were 115 lines of
// report_nbody.txt and 51 of report_pyflate.txt. Compiling with
// `--input txtmode=1` swaps just those figures for a one-line pointer, so the
// text companion reads as prose while the PDF keeps the vector figure.
// Diagrams deliberately do NOT go through this: their labels are the content
// and they export as readable text.
#let text_edition = sys.inputs.at("txtmode", default: "0") == "1"
#let flamefig(path, ..args) = if text_edition {
  align(center, text(size: 9.5pt, style: "italic")[
    (flame graph omitted from the text companion \u{2014} see the PDF edition)
  ])
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
  align(center)[
    #text(size: 21pt, weight: "bold", fill: ink)[#title] #linebreak()
    #v(3pt) #text(size: 12pt)[#subtitle] #linebreak()
    #v(4pt) #text(size: 9pt)[Matan Cohen · Yuval Kogan | Technion | HWSW Final Project]
  ]
  v(9pt)
  body
}
#let note(body) = block(width: 100%, fill: pale, inset: 8pt, radius: 3pt)[#body]
#let result-table(..args) = block(breakable: false)[#table(..args)]
