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
