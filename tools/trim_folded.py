#!/usr/bin/env python3
"""Strip the common leading frames from a folded-stack file.

Every sample in a CPython profile shares a long prefix -- process start-up,
`Py_BytesMain`, the pyperf harness, and the nested `_PyEval_EvalFrameDefault`
ladder -- before anything benchmark-specific appears. Those rows are in 100% of
samples, so they carry no information, but they dominate the height of the
flame graph and push the interesting band off the top of a report page.

Removing a prefix that is present in *every* sample rescales nothing: every
frame keeps its exact sample count and every width is unchanged. Only the
y-origin moves. The number of elided frames is printed so it can be stated in
the figure caption.

Usage:
    trim_folded.py in.folded out.folded [--min-share 1.0]

Folded format (stackcollapse-perf.pl / py-spy): one line per unique stack,
"frame;frame;frame COUNT".
"""
import sys


def parse(path):
    stacks = []
    for line in open(path, encoding="utf-8", errors="replace"):
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


def common_prefix_len(stacks, min_share):
    """Longest frame prefix shared by at least `min_share` of all samples."""
    total = sum(n for _, n in stacks)
    if not total:
        return 0
    depth = 0
    while True:
        # the candidate frame at this depth, by sample weight
        first = None
        agree = 0
        for frames, n in stacks:
            if len(frames) <= depth + 1:      # never strip a stack's own leaf
                continue
            if first is None:
                first = frames[depth]
            if frames[depth] == first:
                agree += n
        if first is None or agree / total < min_share:
            return depth
        depth += 1


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    min_share = 1.0
    if "--min-share" in sys.argv:
        min_share = float(sys.argv[sys.argv.index("--min-share") + 1])

    stacks = parse(src)
    if not stacks:
        sys.exit(f"no stacks parsed from {src}")
    cut = common_prefix_len(stacks, min_share)

    with open(dst, "w", encoding="utf-8") as out:
        for frames, n in stacks:
            kept = frames[cut:] if len(frames) > cut else frames[-1:]
            out.write(";".join(kept) + " " + str(n) + "\n")

    total = sum(n for _, n in stacks)
    deepest = max(len(f) for f, _ in stacks)
    print(f"{src}: {len(stacks)} stacks, {total} samples, max depth {deepest}")
    print(f"  elided {cut} common leading frames -> max depth {deepest - cut}")
    if cut:
        print("  elided prefix:", " -> ".join(stacks[0][0][:cut][:6]),
              "..." if cut > 6 else "")


if __name__ == "__main__":
    main()
