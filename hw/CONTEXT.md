# Hardware accelerators — glossary

Shared vocabulary for the three accelerator modules (`grape_pipeline`, `huffman_engine`,
`mtf_cam`) and their PRD/MAS/uArch/DV documents. A glossary only: no implementation detail.

## Flow

**Checkpoint**:
A stage whose exit requires explicit human approval (PRD, MAS, uArch, DV sign-off).

**Gate**:
The list of measurable criteria a stage must evidence before it can leave `in_progress`.

**ADR (Architecture Decision Record)**:
A short file under `hw/docs/adr/` recording one hard-to-reverse decision and why it was taken.
_Avoid_: design note, rationale doc

## grape_pipeline (nbody)

**Body**:
One point mass with position (3 × FP64), velocity (3 × FP64) and mass (FP64). The benchmark has 5.

**Body state**:
The positions, velocities and masses of all bodies at one instant; what software loads before and
reads back after an invocation.

**Pair**:
An ordered couple of body indices (i, j) whose mutual gravitational interaction is computed.
The benchmark has 10 (all combinations of 5).

**Pair list**:
The programmable sequence of pairs the engine walks once per step, in software-defined order.

**Step**:
One semi-implicit-Euler time step: all pair interactions applied to velocities in pair-list order,
then all positions advanced by dt · v. Equals one iteration of the outer loop in `advance()`.

**Invocation**:
One doorbell-triggered run of NSTEPS consecutive steps on the loaded body state. Equals one
`advance(dt, n)` call.

**Cycles per step**:
The module's primary KPI: busy clock cycles of an invocation divided by NSTEPS.

**Emulation model**:
A software float64 model that performs exactly the hardware's operation sequence (sqrt and
reciprocal instead of `pow`); the RTL must match it bit-for-bit.
_Avoid_: reference model, HW model

**Golden model**:
The benchmark's own `advance()` code, frozen under `golden/`; the acceptance reference with a
tolerance oracle.
_Avoid_: Python model, ground truth

**Energy oracle**:
The acceptance check comparing `report_energy()` of the hardware's final state with that of the
golden model's final state after the same number of steps (not energy conservation: the
integrator itself drifts).

**Doorbell**:
The single register write that starts an invocation.
_Avoid_: start bit, go, kick

## huffman_engine / mtf_cam (pyflate)

**Block**:
One bzip2 block (up to 900 kB of output) or one DEFLATE block; one invocation decodes one block.

**Table**:
One canonical Huffman code (a code-length vector over the alphabet); bzip2 blocks carry 2–6,
DEFLATE blocks carry a literal/length table and a distance table.
_Avoid_: group, tree

**Selector**:
The 3-bit table index that applies to the next group of 50 symbols in a bzip2 block; software
delivers the list already inverse-MTF-decoded.

**Symbol**:
The 9-bit value a Huffman code decodes to: bzip2 alphabet = RUNA, RUNB, MTF indices 1..255, EOB;
DEFLATE = literal 0..255, EOB 256, length codes 257..285, distance codes 0..29.

**Symbol stream**:
The ordered sequence of decoded symbols (plus, in DEFLATE mode, the extra-bit values folded into
length/distance) that the engine emits on its output stream port.

**Table build**:
Deriving count/first_code/base/symtab from a code-length vector inside the engine.

**Aligner**:
The bit-window logic that presents the next MAXLEN stream bits to the decoder and consumes the
matched length (MSB-first for bzip2, bit-reversed LSB-first for DEFLATE).

**Comparator cascade**:
Parallel comparison of the aligned window against every code length's first_code range; the
shortest match wins. The chosen decode architecture (ADR-0003).

**L-vector**:
The output of the MTF + run expansion stage: the byte string the inverse BWT consumes.
_Avoid_: BWT input, tt

**Emulation model** (this module):
`golden/canonical_model.py` — an independent implementation of the comparator-cascade algorithm
and its cycle model; the pyuvm predictor. Never derived from pyflate.

**Golden model** (this module):
`golden/pyflate_ref.py` — the stock pyflate decoder (`dev/pyflate/t0_stock.py`) instrumented to
emit the symbol trace, cross-checked against libbzip2/zlib.
