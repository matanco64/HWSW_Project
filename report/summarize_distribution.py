"""Per-worker timing distributions for the pyperf result JSONs.

The reports quote `mean +- sample SD` over all 120 values of a rigorous run.
That summary hides two things a reader needs:

  1. The shape.  A mean and an SD describe a symmetric distribution; benchmark
     timings are usually right-skewed, and whether the SD is driven by a long
     tail or by a broad body changes how much a small difference means.

  2. The grouping.  The 120 values are not 120 independent observations.  They
     come from 40 worker processes, three values each, and values from one
     worker share that process's address-space layout, CPU placement and page
     cache.  Treating them as independent understates the uncertainty of the
     mean -- by the usual design effect, 1 + (m - 1) * ICC.

So this reports, per file: the quantiles of the pooled values, the spread of
the per-worker means, a one-way variance decomposition into between-worker and
within-worker components, the resulting intraclass correlation, and the
standard error of the mean both naively and corrected for clustering.

    python3 report/summarize_distribution.py results/baseline_nbody.json ...
    python3 report/summarize_distribution.py --json out.json <files...>

Nothing here re-times anything; it only re-reads recorded values.
"""
import argparse
import json
import math
import os
import statistics
import sys


def quantile(sorted_values, q):
    """Linear-interpolated quantile (numpy's default 'linear' method)."""
    if not sorted_values:
        return float('nan')
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return sorted_values[int(pos)]
    return (sorted_values[low] * (high - pos)
            + sorted_values[high] * (pos - low))


def load(path):
    """Return (metadata, [[values of worker 0], [worker 1], ...]).

    pyperf stores one 'run' per worker process. Calibration runs carry only
    warmups and no values; they are not measurements and are excluded.
    """
    with open(path) as fh:
        suite = json.load(fh)
    bench = suite['benchmarks'][0]
    workers = [run['values'] for run in bench['runs'] if run.get('values')]
    meta = dict(suite.get('metadata', {}))
    meta.update(bench.get('metadata', {}) or {})
    return meta, workers


def variance_components(workers):
    """One-way random-effects decomposition of the pooled values.

    Returns (between, within, icc). `between` is the variance attributable to
    the worker a value came from; `within` is the residual variance inside a
    worker. Both are the standard ANOVA estimators for a balanced-ish design;
    `between` is clamped at zero, since a negative variance estimate means
    "no detectable worker effect", not a negative quantity.
    """
    k = len(workers)
    if k < 2:
        return 0.0, statistics.pvariance(workers[0]) if workers else 0.0, 0.0
    n_total = sum(len(w) for w in workers)
    grand = sum(sum(w) for w in workers) / n_total
    means = [statistics.fmean(w) for w in workers]

    ss_between = sum(len(w) * (m - grand) ** 2 for w, m in zip(workers, means))
    ss_within = sum((v - m) ** 2 for w, m in zip(workers, means) for v in w)
    df_within = n_total - k
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / df_within if df_within else 0.0

    # Effective group size for an unbalanced design (Snedecor & Cochran).
    m0 = (n_total - sum(len(w) ** 2 for w in workers) / n_total) / (k - 1)
    between = max(0.0, (ms_between - ms_within) / m0) if m0 else 0.0
    within = ms_within
    total = between + within
    return between, within, (between / total if total else 0.0)


def summarize(path):
    meta, workers = load(path)
    values = sorted(v for w in workers for v in w)
    n = len(values)
    k = len(workers)
    if not n:
        raise SystemExit('%s contains no measured values' % path)

    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    between, within, icc = variance_components(workers)
    per_worker = [statistics.fmean(w) for w in workers]
    m = n / k                                  # mean values per worker

    # Naive SE assumes 120 independent observations. The design effect corrects
    # for the fact that they arrive in correlated groups of three.
    se_naive = sd / math.sqrt(n) if n > 1 else 0.0
    deff = 1 + (m - 1) * icc
    n_eff = n / deff if deff else n
    se_clustered = sd / math.sqrt(n_eff) if n_eff > 1 else se_naive

    rel = os.path.relpath(path).replace(os.sep, '/')
    return {
        'file': rel,
        # Full paths make the columns unreadable at this width; the legend
        # under the tables keeps the mapping.
        'label': os.path.splitext(os.path.basename(rel))[0],
        'backend': meta.get('hwsw_backend'),
        'backend_requested': meta.get('hwsw_backend_requested'),
        'python': meta.get('python_version'),
        'workers': k,
        'values': n,
        'values_per_worker': m,
        'mean_ms': mean * 1e3,
        'sd_ms': sd * 1e3,
        'min_ms': values[0] * 1e3,
        'p25_ms': quantile(values, 0.25) * 1e3,
        'median_ms': quantile(values, 0.50) * 1e3,
        'p75_ms': quantile(values, 0.75) * 1e3,
        'p95_ms': quantile(values, 0.95) * 1e3,
        'max_ms': values[-1] * 1e3,
        'iqr_ms': (quantile(values, 0.75) - quantile(values, 0.25)) * 1e3,
        'worker_mean_min_ms': min(per_worker) * 1e3,
        'worker_mean_max_ms': max(per_worker) * 1e3,
        'worker_mean_sd_ms': (statistics.stdev(per_worker) * 1e3
                              if k > 1 else 0.0),
        'sd_between_ms': math.sqrt(between) * 1e3,
        'sd_within_ms': math.sqrt(within) * 1e3,
        'icc': icc,
        'design_effect': deff,
        'n_effective': n_eff,
        'se_naive_ms': se_naive * 1e3,
        'se_clustered_ms': se_clustered * 1e3,
    }


def report(rows, stream=sys.stdout):
    w = max(len(r['label']) for r in rows)
    print('%-*s %6s %5s %9s %9s %9s %9s %9s'
          % (w, 'file', 'wrk', 'n', 'median', 'IQR', 'p95', 'max', 'mean'),
          file=stream)
    for r in rows:
        print('%-*s %6d %5d %9.3f %9.3f %9.3f %9.3f %9.3f'
              % (w, r['label'], r['workers'], r['values'], r['median_ms'],
                 r['iqr_ms'], r['p95_ms'], r['max_ms'], r['mean_ms']),
              file=stream)
    print(file=stream)
    print('%-*s %9s %9s %7s %7s %9s %9s'
          % (w, 'clustering', 'SD-betw', 'SD-with', 'ICC', 'deff',
             'SE naive', 'SE clust'), file=stream)
    for r in rows:
        print('%-*s %9.3f %9.3f %7.3f %7.2f %9.4f %9.4f'
              % (w, r['label'], r['sd_between_ms'], r['sd_within_ms'],
                 r['icc'], r['design_effect'], r['se_naive_ms'],
                 r['se_clustered_ms']), file=stream)
    print(file=stream)
    for r in rows:
        print('%-*s  %s' % (w, r['label'], r['file']), file=stream)
    print('\nAll times in ms. wrk = value-bearing worker processes; n = measured '
          'values.\nSD-betw/SD-with split the total variance into a '
          'between-worker and a within-worker\ncomponent; ICC is the between '
          'share and deff = 1 + (n/wrk - 1) * ICC is the factor by\nwhich '
          'clustering inflates the variance of the mean. SE clust is the '
          'honest standard\nerror of the mean; SE naive is what treating the '
          'values as independent would give.', file=stream)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+', help='pyperf result JSON files')
    ap.add_argument('--json', metavar='PATH',
                    help='also write the full summary as JSON')
    args = ap.parse_args()

    rows = [summarize(p) for p in args.files]
    report(rows)
    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(rows, fh, indent=2, sort_keys=True)
        print('\nwrote %s' % args.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
