"""How far does full unrolling scale in N?

The landed benchmark's optimization is partial evaluation: the pair schedule is
walked once at import time and emitted as straight-line Python.  That is O(N^2)
in *source size*, not just in time: 12 emitted lines per pair, N(N-1)/2
pairs.
At the benchmark's N = 5 that is 10 pairs / 173 lines and free.  This script
asks what happens when N grows: where the speedup peaks, where it decays, what
the import-time bill is, and whether CPython refuses outright.

Three implementations are compared on the identical initial condition:

  stock  dev/nbody/t0_stock.py, the verbatim pyperformance kernel
  opt    benchmarks/bm_nbody/run_benchmark.py with `--bodies N` applied
  rust   nbody_rs (optional; O(N^2) in time but O(1) in code size, which is
         the whole point of the contrast)

Protocol, same as bench.py: process pinned, GC off inside the timed region,
R rounds interleaved round-robin from a freshly built state, estimator = min
over rounds.  Iteration count is identical across implementations at a given N
and is scaled down as N grows so each measurement stays ~the same wall time:
`steps = round(--work / pairs)`, i.e. constant total pair-updates.

    python sweep_n.py [--bodies 5,10,20,50,100,200] [--work 400000]
                      [--rounds 7] [--no-rust] [--build-only]

`--build-only` skips the timing and reports only the code-generation /
compile() side, which is what you want when hunting for CPython's hard limits.
"""
import argparse
import dis
import gc
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib.machinery                                   # noqa: E402
import importlib.util                                        # noqa: E402

import common                                                # noqa: E402
import t0_stock                                              # noqa: E402

try:
    import hygiene
except ImportError:                                          # pragma: no cover
    hygiene = None

try:
    import nbody_rs
except ImportError:                                          # pragma: no cover
    nbody_rs = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OPT_PATH = os.path.join(REPO, "benchmarks", "bm_nbody", "run_benchmark.py")


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_file_location(name, path, loader=loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# state handling
#
# The generated advance() reads the body lists into locals on entry and writes
# them back on exit, so resetting for the next timing round means putting the
# initial values back into *the same* list objects the closure captured.
# --------------------------------------------------------------------------
def reset(mod, n):
    for (r, v, _m), src in zip(mod.SYSTEM, common.fresh_bodies(n)):
        r[:] = src[0]
        v[:] = src[1]
    mod.offset_momentum(mod.BODIES[mod.DEFAULT_REFERENCE])


def flat(mod):
    out = []
    for (r, v, m) in mod.SYSTEM:
        out.extend(r)
        out.extend(v)
        out.append(m)
    return out


def make_rust(n):
    sysr = nbody_rs.System([(list(r), list(v), m)
                            for (r, v, m) in common.fresh_bodies(n)])
    sysr.offset_momentum(0)
    return sysr


def dump_rust(sysr):
    pos, vel, mass = sysr.state()
    out = []
    for i in range(len(mass)):
        out.extend(pos[3 * i:3 * i + 3])
        out.extend(vel[3 * i:3 * i + 3])
        out.append(mass[i])
    return out


# --------------------------------------------------------------------------
# the code-generation side, timed in its three separate phases
# --------------------------------------------------------------------------
def build_report(n):
    """Emit + compile + exec the N-body kernel, timing each phase."""
    opt = load(OPT_PATH, "_opt_build_%d" % n)
    if n == opt.DEFAULT_BODIES:
        bodies, pairs = opt.SYSTEM, opt.PAIRS
    else:
        opt.BODIES.update(opt._extra_bodies(n))
        opt.SYSTEM[:] = list(opt.BODIES.values())
        opt.PAIRS[:] = opt.combinations(opt.SYSTEM)
        bodies, pairs = opt.SYSTEM, opt.PAIRS

    t = time.perf_counter()
    src = opt._advance_source(bodies, pairs)
    t_gen = time.perf_counter() - t

    t = time.perf_counter()
    code = compile(src, "<nbody-advance>", "exec")
    t_compile = time.perf_counter() - t

    ns = {"_sqrt": opt.sqrt, "_bodies": bodies}
    t = time.perf_counter()
    exec(code, ns)
    t_exec = time.perf_counter() - t

    fn = ns["advance"]
    inner = [c for c in fn.__code__.co_consts if hasattr(c, "co_code")]
    # EXTENDED_ARG census.  CPython's LOAD_FAST/STORE_FAST oparg is one byte;
    # a local whose index is >= 256 needs an EXTENDED_ARG prefix, i.e. a whole
    # extra dispatch.  The emitter uses 8 locals per body, so nlocals crosses
    # 256 at N = 31 -- and that is where the speedup visibly steps down.
    # Instructions are a fixed 2 bytes wide from 3.6 on, so every even offset
    # is an opcode and this census is exact without disassembling 2M
    # instructions.
    code = fn.__code__.co_code
    n_instr = len(code) // 2
    n_ext = sum(1 for i in range(0, len(code), 2)
                if code[i] == dis.EXTENDED_ARG)
    return {
        "n_instr": n_instr,
        "n_ext": n_ext,
        "n": n,
        "pairs": len(pairs),
        "src_lines": src.count("\n"),
        "src_bytes": len(src),
        "co_code": len(fn.__code__.co_code)
                   + sum(len(c.co_code) for c in inner),
        "nlocals": fn.__code__.co_nlocals,
        "nconsts": len(fn.__code__.co_consts),
        "t_gen": t_gen,
        "t_compile": t_compile,
        "t_exec": t_exec,
    }


# --------------------------------------------------------------------------
def emitter_ab(counts, steps_of, rounds):
    """Paired A/B of the two emitter variants: temporaries hoisted or not.

    Both come out of the landed file's own `_advance_source(..., hoist=)`, so
    this measures exactly the thing that ships, not a re-implementation.
    """
    built = {}
    for n in counts:
        m = load(OPT_PATH, "_opt_ab_%d" % n)
        m._configure(n)              # gives m.SYSTEM/m.PAIRS the N system
        fns = {}
        for key, h in (("plain", False), ("hoist", True)):
            src = m._advance_source(m.SYSTEM, m.PAIRS, hoist=h)
            ns = {"_sqrt": m.sqrt, "_bodies": m.SYSTEM}
            exec(compile(src, "<ab>", "exec"), ns)
            code = ns["advance"].__code__
            fns[key] = (ns["advance"], len(code.co_code),
                        sum(1 for i in range(0, len(code.co_code), 2)
                            if code.co_code[i] == dis.EXTENDED_ARG))
        built[n] = (m, fns)

    print("\n--- emitter A/B: per-pair temporaries hoisted to low slots ---")
    print("%4s %8s %11s %11s %9s %10s %10s"
          % ("N", "steps", "plain ms", "hoist ms", "gain", "EXT plain",
             "EXT hoist"))
    for n in counts:
        m, fns = built[n]
        steps = steps_of[n]
        best = {"plain": float("inf"), "hoist": float("inf")}
        for _ in range(rounds):
            for key in ("plain", "hoist"):
                fn = fns[key][0]
                reset(m, n)
                best[key] = min(best[key],
                                _timed(lambda: fn(0.01, steps)))
        instr = {k: fns[k][1] // 2 for k in fns}
        print("%4d %8d %11.3f %11.3f %8.3fx %9.1f%% %9.1f%%"
              % (n, steps, best["plain"] * 1e3, best["hoist"] * 1e3,
                 best["plain"] / best["hoist"],
                 100.0 * fns["plain"][2] / instr["plain"],
                 100.0 * fns["hoist"][2] / instr["hoist"]))


def _timed(fn):
    gc.collect()
    gc.disable()
    t = time.perf_counter()
    fn()
    dt = time.perf_counter() - t
    gc.enable()
    return dt


def sweep_times(counts, steps_of, rounds, use_rust):
    """Time every (N, implementation) pair, interleaved across *everything*.

    Measuring one N to completion and then the next lets slow drift on a shared
    machine masquerade as an N effect -- the first version of this script
    reported N = 100 as 70% slower than N = 200 at identical total work, which
    is physically impossible and was pure drift.  So the outer loop is the
    round and every (N, impl) cell is visited once per round.  Ratios are also
    formed *within* a round and then reduced, so a slow round cancels.
    """
    mods = {}
    for n in counts:
        m = load(OPT_PATH, "_opt_run_%d" % n)
        m._configure(n)
        mods[n] = m

    raw = {(n, k): [] for n in counts for k in ("stock", "opt", "rust")}
    ratio = {(n, k): [] for n in counts for k in ("opt", "rust")}
    exact = {}
    for _ in range(rounds):
        for n in counts:
            steps = steps_of[n]
            st = t0_stock.make_state(n)
            ts = _timed(lambda: t0_stock.advance(st, 0.01, steps))

            opt = mods[n]
            reset(opt, n)
            to = _timed(lambda: opt.advance(0.01, steps))

            raw[(n, "stock")].append(ts)
            raw[(n, "opt")].append(to)
            ratio[(n, "opt")].append(ts / to)

            tr = None
            if use_rust:
                sr = make_rust(n)
                tr = _timed(lambda: sr.advance(0.01, steps))
                raw[(n, "rust")].append(tr)
                ratio[(n, "rust")].append(ts / tr)

            ref = t0_stock.dump(st)
            ok = (ref == flat(opt))
            ok_rs = (ref == dump_rust(sr)) if use_rust else None
            finite = all(x == x and abs(x) != float("inf") for x in ref)
            prev = exact.get(n)
            exact[n] = (ok if prev is None else (prev[0] and ok),
                        ok_rs if prev is None else (prev[1] and ok_rs
                                                    if ok_rs is not None
                                                    else None),
                        finite if prev is None else (prev[2] and finite))
    return raw, ratio, exact


def _median(v):
    s = sorted(v)
    k = len(s) // 2
    return s[k] if len(s) % 2 else 0.5 * (s[k - 1] + s[k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bodies", default="5,10,20,50,100,200")
    ap.add_argument("--work", type=int, default=400000,
                    help="target pair-updates per measurement; steps is "
                         "derived so every N does the same total work")
    ap.add_argument("--steps", type=int, default=0,
                    help="override: use this fixed step count at every N")
    ap.add_argument("--rounds", type=int, default=7)
    ap.add_argument("--no-rust", action="store_true")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--emitter-ab", action="store_true",
                    help="A/B the two emitter variants instead of the sweep")
    a = ap.parse_args()
    counts = [int(x) for x in a.bodies.split(",") if x.strip()]
    use_rust = (nbody_rs is not None) and not a.no_rust

    if hygiene is not None and not a.build_only:
        print("hygiene: %s" % hygiene.tune())
    print("python %s | rounds=%d | rust=%s | estimator = min over rounds"
          % (sys.version.split()[0], a.rounds, "yes" if use_rust else "no"))

    print("\n--- code generation (import-time, outside the timed region) ---")
    print("%4s %7s %10s %8s %10s %8s %7s %8s %8s %10s %9s"
          % ("N", "pairs", "src lines", "src MB", "co_code B", "ops/pair",
             "nlocals", "EXT_ARG", "gen ms", "compile ms", "total ms"))
    builds = {}
    for n in counts:
        try:
            b = build_report(n)
        except Exception as exc:                             # noqa: BLE001
            print("%4d  *** %s: %s" % (n, type(exc).__name__, exc))
            continue
        builds[n] = b
        tot = b["t_gen"] + b["t_compile"] + b["t_exec"]
        print("%4d %7d %10d %8.3f %10d %8.1f %7d %7.1f%% %8.1f %10.1f %9.1f"
              % (n, b["pairs"], b["src_lines"], b["src_bytes"] / 1e6,
                 b["co_code"], b["n_instr"] / float(b["pairs"]), b["nlocals"],
                 100.0 * b["n_ext"] / b["n_instr"],
                 b["t_gen"] * 1e3, b["t_compile"] * 1e3, tot * 1e3))
    if a.build_only:
        return 0

    live = [n for n in counts if n in builds]
    steps_of = {n: (a.steps or max(4, int(round(a.work /
                                               (n * (n - 1) // 2)))))
                for n in live}
    if a.emitter_ab:
        emitter_ab(live, steps_of, a.rounds)
        return 0
    raw, ratio, exact = sweep_times(live, steps_of, a.rounds, use_rust)

    print("\n--- steady-state advance(), min of %d interleaved rounds ---"
          % a.rounds)
    print("%4s %7s %8s %11s %11s %11s %10s %10s %9s %7s"
          % ("N", "pairs", "steps", "stock ms", "opt ms", "rust ms",
             "opt x", "opt x(med)", "rust x", "exact"))
    for n in live:
        s = min(raw[(n, "stock")])
        o = min(raw[(n, "opt")])
        rs = min(raw[(n, "rust")]) if use_rust else None
        ex_o, ex_r, finite = exact[n]
        print("%4d %7d %8d %11.3f %11.3f %11s %9.3fx %9.3fx %8s %7s"
              % (n, n * (n - 1) // 2, steps_of[n], s * 1e3, o * 1e3,
                 ("%.3f" % (rs * 1e3)) if use_rust else "-",
                 s / o, _median(ratio[(n, "opt")]),
                 ("%.1fx" % (s / rs)) if use_rust else "-",
                 ("yes" if ex_o else "NO")
                 + ("" if ex_r is not False else "/rustNO")))
        if not finite:
            print("     *** WARNING: non-finite state at N=%d" % n)
    print("\n'opt x' is min(stock)/min(opt) over rounds, the same estimator "
          "bench.py uses;\n'opt x(med)' is the median of the *paired* "
          "within-round ratios, which is\nimmune to drift.  They should "
          "agree; if they do not, the run was noisy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
