# `nbody_rs` - native `advance()` for the pyperformance `nbody` benchmark

**Status: BUILT, VERIFIED, MEASURED** on CPython 3.10.21 (WSL2 Ubuntu 24.04),
which is the closest available stand-in for the course VM CPython 3.10.12.

* **Bit-for-bit identical to stock CPython** after 20,000 steps: all 35 state
  floats and `report_energy()` compare `==`, max |delta| = 0.0. The
  floating-point contract below held exactly as designed.
* **Kernel speedup 25.8x** (`advance(0.01, 20000)`: 92.5 ms -> 3.59 ms, min of
  9 interleaved rounds; provisional, measured on a contended machine).
* **FFI crossing cost 91 ns/call**, i.e. 2.5e-5 of one `advance()` call. The
  coarse-boundary design is validated by measurement, not asserted.

Reproduce with `dev/nbody/rs_check.py`. Nothing in the project >=7% speedup
claim depends on this crate: the pure-Python tier already delivers ~1.75x on
its own, and the Rust path is deliberately not wired into the shipped
`run_benchmark.py` (see `dev/nbody/FINDINGS.md` section 6).

## Build (inside the course QEMU VM: Ubuntu 22.04, CPython 3.10.12, x86-64)

```bash
curl https://sh.rustup.rs -sSf | sh          # rustc + cargo, one time
python3 -m pip install maturin

cd rust/nbody
maturin build --release                       # -> target/wheels/nbody_rs-0.1.0-cp310-cp310-linux_x86_64.whl
python3 -m pip install target/wheels/nbody_rs-0.1.0-cp310-*.whl
# or, into the venv you are benchmarking with:
maturin develop --release
```

Build **inside the VM**. The wheel is per-interpreter and per-architecture;
a wheel built on another host will not load, and building in-guest also
sidesteps manylinux/glibc mismatch entirely. After the first build the
`~/.cargo` cache makes rebuilds offline; for a fully air-gapped VM run
`cargo vendor` once and `maturin build --offline`.

To wire it into `pyperformance run --manifest`, add the wheel to
`benchmarks/bm_nbody/requirements.txt`; pyperformance installs a benchmark's
requirements into its per-run venv automatically. Note that pyperf runs the
benchmark in **worker subprocesses**, so the extension has to be pip-installed
into the measured venv - `PYTHONPATH` will not do, pyperf strips the
environment.

## Boundary design

One FFI crossing per `advance()` call.

```
Python                                  Rust
------                                  ----
sys = nbody_rs.System(SYSTEM)   ------> own pos[3N], vel[3N], mass[N], pairs
sys.offset_momentum(0)          ------> (once, at setup)
sys.advance(0.01, 20000)        ------> 20,000 steps x 10 pairs, no crossings
sys.energy()                    <------ one f64
sys.state()                     <------ 35 f64, only when Python needs to look
```

A benchmark iteration is `report_energy(); advance(0.01, 20000);
report_energy()` - so **three crossings per iteration** carrying at most 35
doubles each, against 200,000 pair updates of work. A PyO3 call costs ~25-60 ns
plus per-argument conversion; the work behind it is ~10-20 ms. The boundary is
free by a factor of ~10<sup>5</sup>.

The alternative shape - pass the 5x7 floats in and out on every call - would
also be perfectly fine at this size (280 bytes each way). Resident state was
chosen because it makes the hardware analogy exact: the `#[pyclass]` **is** the
accelerator's register file, `advance(dt, n)` **is** the doorbell write with a
step-count register, and `state()` **is** the read-back window. The FFI
boundary drawn here is the same boundary the MMIO driver would draw.

## Expected speedup, and where the number comes from

The Python kernel executes ~1,484 bytecodes per integration step (measured,
`dev/nbody/opcount.py`). At CPython 3.10's roughly 20-60 ns per bytecode -
each arithmetic op going through generic `binary_op1` dispatch, allocating and
freeing a boxed `PyFloatObject` - a step costs ~10-12 us, which matches the
observed 230 ms for 20,000 steps in the course VM.

The same step in Rust is ~230 scalar f64 operations on unboxed values in
registers: 10 pairs x (3 sub, 3 mul, 2 add, 1 `pow`, 3 mul, 6 mul, 6 add/sub)
plus 15 fused position updates. Everything except `pow` is 3-5 cycle latency
and pipelined; `pow` is the only real cost at ~40-80 cycles, x10 per step.
Estimate ~1,200-1,800 cycles/step ~ 0.4-0.6 us at 3 GHz.

**Predicted kernel speedup was 20-40x. MEASURED: 25.8x** on CPython 3.10.21
(`advance(0.01, 20000)`: 92.5 ms -> 3.59 ms, min of 9 interleaved rounds), so
the estimate above was sound. Since `advance()` is ~95 % of the benchmark,
Amdahl caps the end-to-end win at 1/(0.05 + 0.95/25.8) = **~12x**; expect the
measured benchmark-level figure to land in the **8-12x** range, the residue
being `report_energy()` (still Python), the pyperf harness, and the three
crossings per iteration.

Two calibration points: PyPy JIT alone gets ~13x on this benchmark, and the
pure-Python partial-evaluation tier in this project already gets 1.75x by
removing ~40 % of the bytecodes without removing the interpreter. AOT Rust on
unboxed f64 landing at ~26x is exactly where those two bracket it.

The remaining cost inside the Rust kernel is the ten `pow()` calls per step -
which is precisely the operation the GRAPE-style accelerator replaces with an
rsqrt LUT seed plus two Newton-Raphson iterations.

If bit-identity is dropped (see the FP contract in `src/lib.rs`), replacing
`powf(-1.5)` with `dt / (dsq * dsq.sqrt())` removes the libm call - the single
largest remaining cost - for perhaps another 1.5-2x on the kernel. That is the
trade to state explicitly in the report rather than to take silently.

## Verification: DONE

`dev/nbody/rs_check.py`, CPython 3.10.21, 20,000 steps from the benchmark
initial condition:

```
   state bit-identical : True      (all 35 floats compare ==, max |delta| 0.0)
   energy bit-identical: True      (-0.16908926275527172 both sides)
   kernel speedup      : 25.8x     (92.512 ms -> 3.587 ms, min of 9 rounds)
   FFI crossing cost   : 91 ns/call = 2.5e-5 of one advance() call
```

So the floating-point contract held exactly as written: `f64::powf(-1.5)` did
resolve to the same glibc `pow` CPython calls, and LLVM contracted and
reassociated nothing. The honest claim is **equality**, not a tolerance.

Still to do on the course VM once it is reachable: rebuild the wheel there,
re-run `rs_check.py` to confirm bit-identity on Ubuntu 22.04 glibc 2.35, and
record a `perf record -g` flame graph (the crate sets `debug = true` so Rust
frames symbolize) for the before/after visual.

## Relation to the hardware proposal

The datapath this crate describes per pair - 3 subtracts -> 3 multiplies +
2 adds -> one `x^(-3/2)` -> 2 multiplies -> 6 multiply-accumulates - is exactly
the GRAPE-style gravity pipeline in the hardware chapter. The `pow` that
dominates the native kernel is the operation the accelerator replaces with an
rsqrt LUT seed plus two Newton-Raphson iterations, which is where the
fixed-function design earns its win over the compiled one. The Rust kernel is
therefore both an optimisation tier and the behavioural spec for the
accelerator.
