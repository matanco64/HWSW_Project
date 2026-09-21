// Names + ID numbers, on their own page, as HW1 and HW2 did.
//
//   typst compile --input matan-id=<ID> --input yuval-id=<ID> report/ids.typ ids.pdf
//
// make_submission.sh supplies the real numbers from the gitignored
// report/ids.local and puts the result in the archive. Nothing here is ever
// committed: this repository is public, and git history is permanent.
#let matan-id = sys.inputs.at("matan-id", default: "<ID>")
#let yuval-id = sys.inputs.at("yuval-id", default: "<ID>")
#let ink = rgb("#18344a")

#set page(paper: "a4", margin: 2cm)
#set text(font: "Libertinus Serif", size: 11pt, lang: "en")

#align(center + horizon)[
  #text(size: 18pt, weight: "bold", fill: ink)[HWSW Final Project] \
  #v(0.35em)
  #text(size: 12pt)[Benchmark Optimization, Analysis and Hardware Acceleration] \
  #v(0.4em)
  #text(size: 11pt)[pyflate · nbody] \
  #v(2.4em)
  #text(size: 13pt)[
    Matan Cohen — ID: #matan-id \
    #v(0.45em)
    Yuval Kogan — ID: #yuval-id
  ] \
  #v(2.4em)
  #text(size: 10pt)[Technion — Israel Institute of Technology]
]
