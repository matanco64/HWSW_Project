#!/usr/bin/env python3
"""Make a folded-stack file plottable at a sane height.

A flame graph is as tall as the single deepest stack in the file, however rare
that stack is. Our profiles are pathological that way. py-spy on the optimised
pyflate run collects 104 samples: the deepest is 60 frames, while the band that
actually carries the benchmark is 15. So three quarters of the height existed
to draw towers one sample wide, which is what made these eat a whole page.

Looking at those towers settles what to do with them. Every one of them is
module import machinery:

    _find_and_load -> _load_unlocked -> exec_module -> <module> -> re._compile
    ... -> namedtuple / enum._missing_ / TextWrapper

py-spy starts sampling at process start, so it catches CPython importing `re`,
`enum`, `collections` and friends before the benchmark loop is ever entered.
Those samples are startup, not workload. Dropping them is not a cosmetic
truncation, it excludes a phase the figure was never meant to show:

    profile                samples   dropped as startup   max depth
    pyspy_nbody_stock          304        5  (1.6%)        36 -> 12
    pyspy_nbody_opt            187        5  (2.7%)        41 -> 16
    pyspy_pyflate_stock        404       13  (3.2%)        61 -> 18
    pyspy_pyflate_opt          104        7  (6.7%)        60 -> 15

Nothing is rescaled. Every surviving frame keeps its exact sample count, so
every width in the plot is unchanged; only rows disappear.

Two further reductions are available for the perf (C-level) captures, which
start at depth ~173 thanks to interpreter startup and the nested
_PyEval_EvalFrameDefault ladder:

  --dominant-root  keep only stacks rooted in the process we profiled.
                   `perf script` interleaves every process that ran, so stray
                   samples arrive from `uname`, `file`, etc.
  --prefix         drop leading frames shared by >= --min-share of samples. A
                   frame in (almost) every sample carries no information but
                   costs a row of height. Off by default: on the py-spy
                   profiles the shared prefix *is* the call path worth showing
                   (bench_nbody -> advance), and trimming it leaves a one-row
                   figure. The threshold is 0.99 rather than 1.0 because at
                   1.0 a single stray stack blocks the whole trim.

Every reduction is reported on stderr so the numbers can go in the caption.

Usage:
    trim_folded.py in.folded out.folded [--keep-startup] [--dominant-root]
                                        [--prefix] [--min-share 0.99]
                                        [--cap SHARE]
"""
import argparse
import collections
import sys

# frames that only ever appear while CPython is importing modules
STARTUP_MARKERS = ("importlib._bootstrap", "frozen zipimport")


def parse(path):
    stacks = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            stack, _, count = line.rpartition(" ")
            try:
                n = int(count)
            except ValueError:
                continue
            if stack:
                stacks.append((stack.split(";"), n))
    return stacks


def drop_startup(stacks):
    kept, dropped = [], 0
    for frames, n in stacks:
        joined = ";".join(frames)
        if any(m in joined for m in STARTUP_MARKERS):
            dropped += n
        else:
            kept.append((frames, n))
    return kept, dropped


def keep_dominant_root(stacks):
    roots = collections.Counter()
    for frames, n in stacks:
        roots[frames[0]] += n
    if not roots:
        return stacks, None, 0
    root = roots.most_common(1)[0][0]
    kept = [(f, n) for f, n in stacks if f[0] == root]
    dropped = sum(n for f, n in stacks if f[0] != root)
    return kept, root, dropped


def common_prefix_len(stacks, min_share):
    """Longest leading run of frames shared by >= min_share of samples."""
    total = sum(n for _, n in stacks)
    if not total:
        return 0
    depth = 0
    while True:
        agree = collections.Counter()
        # never strip a stack down to nothing: a stack with only one frame
        # left to give does not get a vote
        for frames, n in stacks:
            if len(frames) >= depth + 2:
                agree[frames[depth]] += n
        if not agree or agree.most_common(1)[0][1] / total < min_share:
            return depth
        depth += 1


def cap_depth(stacks, keep_share):
    """Shallowest cut leaving >= keep_share of samples untruncated."""
    total = sum(n for _, n in stacks)
    hist = collections.Counter()
    for frames, n in stacks:
        hist[len(frames)] += n
    cum = 0
    for d in sorted(hist):
        cum += hist[d]
        if cum / total >= keep_share:
            return d
    return max(hist)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--keep-startup", action="store_true",
                    help="do not drop import-machinery samples")
    ap.add_argument("--dominant-root", action="store_true",
                    help="keep only stacks rooted in the heaviest root frame")
    ap.add_argument("--prefix", action="store_true",
                    help="also strip the common leading frames")
    ap.add_argument("--min-share", type=float, default=0.99)
    ap.add_argument("--cap", type=float, default=None, metavar="SHARE",
                    help="truncate tips, keeping SHARE of samples whole")
    args = ap.parse_args()

    stacks = parse(args.src)
    if not stacks:
        sys.exit("no stacks parsed from %s" % args.src)
    total0 = sum(n for _, n in stacks)
    deep0 = max(len(f) for f, _ in stacks)
    notes = []

    if not args.keep_startup:
        stacks, dropped = drop_startup(stacks)
        if not stacks:
            sys.exit("%s: every stack looked like startup, refusing to empty "
                     "the file (use --keep-startup)" % args.src)
        if dropped:
            notes.append("dropped %d startup samples (%.2f%%) taken during "
                         "module import" % (dropped, 100.0 * dropped / total0))

    if args.dominant_root:
        stacks, root, dropped = keep_dominant_root(stacks)
        if dropped:
            notes.append("dropped %d samples (%.2f%%) not rooted at %r"
                         % (dropped, 100.0 * dropped / total0, root))

    if args.prefix:
        cut = common_prefix_len(stacks, args.min_share)
        if cut:
            prefix = stacks[0][0][:cut]
            notes.append("elided %d common leading frames: %s"
                         % (cut, " -> ".join(prefix[:4])
                            + (" -> ..." if cut > 4 else "")))
            stacks = [(f[cut:] if len(f) > cut else f[-1:], n)
                      for f, n in stacks]

    if args.cap is not None:
        cap = cap_depth(stacks, args.cap)
        tot = sum(n for _, n in stacks)
        truncated = sum(n for f, n in stacks if len(f) > cap)
        if truncated:
            notes.append("capped at depth %d, truncating the tips of %d "
                         "samples (%.2f%%)"
                         % (cap, truncated, 100.0 * truncated / tot))
        stacks = [(f[:cap], n) for f, n in stacks]

    # trimming can make previously distinct stacks identical; merge them so
    # flamegraph.pl does not draw the same frame twice side by side
    merged = collections.OrderedDict()
    for frames, n in stacks:
        key = ";".join(frames)
        merged[key] = merged.get(key, 0) + n
    with open(args.dst, "w", encoding="utf-8") as out:
        for stack, n in merged.items():
            out.write("%s %d\n" % (stack, n))

    kept = sum(n for _, n in stacks)
    deep1 = max(len(f) for f, _ in stacks)
    print("%s: %d -> %d samples, depth %d -> %d"
          % (args.src.rsplit("/", 1)[-1], total0, kept, deep0, deep1),
          file=sys.stderr)
    for note in notes:
        print("  " + note, file=sys.stderr)


if __name__ == "__main__":
    main()
