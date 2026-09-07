#import "style.typ": *
#show: report.with("Benchmark Report: pyflate",
  "A small link budget, a compressed payload, and a lot of work between the bits")

*Somewhere between a spacecraft and a ground station there is a link budget measured in
kilobits.* Compression makes the most of it; decompression turns the arriving bits back into
useful data. This benchmark gives that quiet half of the job to Python: read a bit stream,
recover symbols, and undo several transformations. Its Huffman matcher looks like the obvious
place to start. Measuring it led us to improvements across the whole decoding pipeline,
then a Rust extension that executes the symbol decoder through one call per block.

= 1. Workload and result

Despite its name, the measured `pyflate` workload is *bzip2*, not DEFLATE.
Each iteration decompresses `interpreter.tar.bz2` from *67,562 bytes to 399,360 bytes*;
the harness checks the original MD5 outside the timer. The Python tier uses the standard library rather than calling
a native decompression library. Its main structures are an integer bit buffer, Huffman tables,
a move-to-front (MTF) alphabet, Burrows-Wheeler transform (BWT) index vectors and output buffers.

#note[*One block, six Huffman tables, 148,271 symbols.* The decoder switches tables every
50 symbols. Huffman decoding, move-to-front and RUNA/RUNB expansion produce a 336,184-byte
L-vector. Inverse BWT and final RLE4 expansion produce the 399,360-byte output.]

#figure(image("fig/pyflate_stages.svg", width: 100%),
  caption: [The bzip2 path. RUNA/RUNB and move-to-front are handled together in the symbol loop.
  The native kernel covers the same combined boundary proposed for hardware.])

#result-table(columns: (1.7fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Configuration*], [*Mean ± SD*], [*vs stock*]),
  [Stock Python], [1,129.89 ± 12.68 ms], [1.00×],
  [Optimized Python], [288.00 ± 3.22 ms], [3.92×],
  [*Python + Rust extension*], [*173.59 ± 2.15 ms*], [*6.51×*],
)

*Our final software path is 6.51× faster than stock: an 84.6% runtime reduction.*
Python improvements provide 3.92×; the Rust symbol decoder adds *1.66×* over that optimized
baseline. Both tiers exceed the course's 7% improvement requirement and match
`bz2.decompress` byte for byte, passing the unchanged MD5 check. Rust handles the blue
stage above; block headers, inverse BWT and RLE4 remain in Python.

#note[*Measurement scope.* Course QEMU/KVM VM, Ubuntu 22.04, release CPython 3.10.12,
pyperf 2.10.0; 120 measured values per configuration, collected sequentially on guest CPU 0.
The current Rust source was rebuilt and checked on this VM. Source:
`results/vm_release_20260907/pyflate_{stock,python,native}.json`.
Development profiles and ablations are labeled separately.]

#pagebreak()
= 2. Profiling: the whole decoding pipeline

The stock Python-frame profile highlights Huffman decoding and bit-buffer work, with
move-to-front and inverse BWT alongside them. Development instrumentation found a mean of
about five entries visited by the symbol matcher, despite its table capacity of 258.
A lookup table can remove this scan, but the measured scan is short; per-symbol interpreter
work and the later transformations also deserve attention.

#figure(image("fig/print_pyflate_stock.svg", width: 100%),
  caption: [Full stock Python-frame flame graph, retaining startup and harness context.
  Numbered outlines identify exactly the call paths enlarged on the right. Inclusive
  percentages use the original whole-profile denominator; nested shares overlap.])

A separate *Windows / CPython 3.12.6* cProfile run gives
`find_next_symbol` 0.519 s cumulative out of 1.186 s (43.8%), including its bit-reader
callees. `decode_huffman_block` has 0.241 s *self* time and 1.172 s *cumulative* time:
most of its inclusive cost is in functions it calls. Source: `dev/pyflate/FINDINGS.md` §3.

#figure(image("fig/huffman_tree.svg", width: 100%),
  caption: [Illustrative canonical Huffman codes. Codes of equal length are consecutive;
  length-indexed ranges identify the symbol without scanning individual candidates.
  The optimized implementation adds a primary lookup for short codes.])

#pagebreak()
= 3. Changes that shipped

- *Reduce per-byte overhead:* read the compressed input once, refill the bit window in
  chunks, bind hot values to locals and accumulate bytes without allocating an object per byte.
- *Decode canonical Huffman codes:* use length-indexed tables and a primary lookup table
  with a fallback for longer codes. Table construction is amortized over the block.
- *Improve the back end:* replace comparison sorting with counting-sort BWT construction;
  reverse the MTF list so updates move O(rank) entries; use regex-assisted RLE4 expansion
  to reduce Python loop iterations. The byte scan/output work is still linear overall.

#result-table(columns: (2fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Component reverted from T3*], [*Runtime*], [*Added cost*]),
  [None (full T3)], [175.5 ms], [—],
  [Primary Huffman lookup], [185.6 ms], [+10.1 ms],
  [Regex-assisted RLE4], [207.7 ms], [+32.3 ms],
  [Counting-sort BWT], [214.0 ms], [+38.6 ms],
)

*Ablation scope:* Windows / CPython 3.12.6, best of seven; `dev/pyflate/FINDINGS.md` §2b.
These are development measurements, not VM timings. Each row reverts one component;
the costs need not add. In this experiment, each back-end change contributes more than the
primary Huffman table. This motivates optimizing the pipeline rather than the matcher alone.

#figure(image("fig/print_pyflate_opt.svg", width: 100%),
  caption: [Full optimized *Python* profile, before native offload. Inverse BWT and its
  index-table construction remain visible. Matcher work was inlined, so its old function
  frame disappears without implying that Huffman decoding is free.])

#pagebreak()
= 4. Native execution: what improves, what remains

Our Rust/PyO3 `BlockDecoder` handles the bit reader, Huffman decode, MTF and RUNA/RUNB
expansion. Header parsing, inverse BWT, RLE4 and MD5 remain in Python. One block-level call
returns the L-vector and the ending bit position; checking both catches output errors and
stream desynchronization.

#result-table(columns: (1.7fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Same benchmark file*], [*Mean ± SD*], [*vs Python*]),
  [Python backend], [288.00 ± 3.22 ms], [1.00×],
  [Native decode backend], [173.59 ± 2.15 ms], [*1.66×*],
)

These are the same 120-value measurements summarized on page 1, covering the complete
benchmark. The new VM build includes the submitted Rust refactor.
`HWSW_BACKEND=python|native|auto` selects the implementation; native mode requires the extension,
while auto mode falls back. Pyperf workers need `--inherit-environ HWSW_BACKEND`.

*The submitted Rust source was rebuilt on the VM.* Ten Rust unit tests and seven blocks
across five Python/`bz2` fixtures passed, including exact ending bit positions. A dispatch
check confirmed that `native` and `auto` load the new extension and call it once per block.
The crate separates Python bindings, bit reading, Huffman tables, block decoding and trace
serialization; the Python API is unchanged. After installing the current build,
`script_pyflate.sh native` runs this tier.

== Matched-work CPU counters

These are medians of three warm-loop VM runs, each decoding the input 16 times, divided by
16. Both backends produced the same output digest. They are a separate experiment from the
rigorous timing table above, with acknowledged counter gating after setup (Appendix A2).

#result-table(columns: (1.8fr, 1fr, 1fr), align: (left, right, right),
  table.header([*Metric per complete decode*], [*Python*], [*Hybrid native*]),
  [Elapsed time], [288.68 ms], [174.44 ms],
  [Instructions], [1,947.94 M], [1,171.65 M],
  [Cycles], [675.92 M], [404.24 M],
  [IPC], [2.88], [2.90],
  [Branches], [349.43 M], [207.30 M],
  [Branch misses (rate)], [544,260 (0.156%)], [301,458 (0.145%)],
  [Generic cache references], [1.749 M], [1.686 M],
  [Generic cache misses (rate)], [69,322 (3.964%)], [52,842 (3.133%)],
)

Native decoding reduces instructions by *39.9%*, cycles by *40.2%* and branch misses by
*44.6%*, while IPC changes little. The approximately 1.65× speedup in this experiment
comes mainly from removing interpreter work. Generic cache misses fall *23.8%*, a smaller
reduction than instructions: the remaining Python BWT/RLE4 pipeline still processes the
whole block. Aggregate counters cannot attribute misses to a particular stage. L1 events
are omitted because an earlier capture returned invalid load counts.

== Offload limits and the next target

Amdahl's law gives $S = 1 / ((1 - f) + f / s)$ for kernel speedup $s$ and offloaded fraction
$f$ of *optimized Python* runtime. Even infinite symbol-decoder speed leaves BWT and RLE4.
Unlike nbody's native integration loop, this offload leaves over a billion instructions
per decode in a largely Python pipeline. The next target is the *whole inverse BWT*, including table
construction, not just its dependent traversal. Earlier VM phase timings put them at
137.7 ms and 47.8 ms respectively (Appendix A3). A native port and working-set sweep would
test whether memory latency then becomes limiting; the present data do not establish that.

#pagebreak()
= 5. Hardware acceleration: current proposal

The hardware boundary comprises `huffman_engine` followed by `mtf_cam`. Together they
produce the same L-vector as the native decoder. Software keeps block headers, inverse BWT,
RLE4 and MD5. A regular decoder datapath and a coarse block-level submission are the main
co-design opportunities.

#figure(image("fig/decode_report.svg", width: 100%),
  caption: [AXI4-Lite configures both modules; AXI4-Stream carries data. The symbol stream stays
  on chip. Platform DMA returns the L-vector to software.])

== Huffman engine

A bit aligner feeds a canonical-code comparator/lookup datapath. The selector controller
changes the active table every 50 symbols. The current interface specifies a 32-bit compressed
input stream, an 8-bit selector stream, and 32-bit output beats containing a 9-bit bzip2 symbol
plus type fields. A 32-bit AXI4-Lite window holds controls, `START_BIT`, lengths and counters.
It supports up to six tables and a maximum bzip2 code length of 20 bits.

The target is at most 1.10 cycles per symbol, including table construction and switches,
with an unstalled benchmark-block model of 153,121 cycles. At the *50 MHz clock target*,
that model is 3.06 ms for this module. This is not an achieved frequency or a measured
end-to-end hardware runtime.

== MTF and run expansion

The input is a *rank*, so the decoder selects an indexed alphabet entry and shifts preceding
entries.
The current proposal maintains up to 256 entries and expands RUNA/RUNB groups through a
buffered output packer. The default output width is eight bytes (64-bit data plus byte enables).
It targets one MTF symbol per cycle for any valid rank.

Measured mean rank 7.17 characterizes this input; the one-symbol-per-cycle requirement also
covers large ranks. The specified area/throughput sweep varies output width
W = 4, 8, 16 and FIFO depth. The default module model is 157,560 cycles, or 3.15 ms at
50 MHz. The two modules stream concurrently; their individual modeled latencies cannot
simply be added or substituted for an integrated back-pressure simulation.

#note[*Implementation status.* Requirements and architecture are approved for both modules.
Microarchitecture, RTL, verification, PPA and integration are still open in the recorded
hardware status. Formal MTF invariants are planned, not completed proofs. Drivers and
platform DMA remain integration work. No measured area, clock or power benefit is claimed.]

= 6. Conclusion

The delivered Python-plus-Rust path decompresses the input in *173.59 ms*, achieving
*6.51× over stock* with byte-exact output. Python improvements provide 3.92× and the native
decoder adds 1.66×, leaving BWT and RLE4 as the next software targets. The hardware proposal
follows the same block-level interface; its integrated performance and cost remain to be
demonstrated.

#text(size: 9pt)[*Evidence:* `hw/huffman_engine/docs/{prd,mas}.md`,
`hw/mtf_cam/docs/{prd,mas}.md`, and `hw/PROGRESS.md` (2026-09-05).
Methods and supporting profiles: *report_appendix.pdf*.
Repository: #link("https://github.com/matanco64/HWSW_Project")[HWSW_Project].]
