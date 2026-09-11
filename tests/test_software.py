"""Regression tests for the software correctness machinery.

Each test pins down a failure that actually happened, or one a checker exists
to catch, so that an edit reintroducing it fails here rather than on the
course VM hours into a run:

  verify.py      the landed benchmark is gated on exact equality; a missing
                 stock reference is a failure, not a skip; the Python kernel is
                 what gets checked even with nbody_rs installed (the course VM
                 reported an 18 AU "divergence" at N=10 because it was not)
  rs_check.py    exact contract by default; --tolerance moves the gate
  benchmarks     native metadata hashes the compiled .so, not maturin's
                 identical-every-build __init__.py; HWSW_BACKEND reaches pyperf
                 workers; native mode leaves a correct advance() at any N
  report tools   the variance decomposition recovers a known ICC; profile sums
                 match the figures the reports quote; the text-export check
                 rejects shifted rows and invalid UTF-8
  runner         assert_backend rejects a wrong, unpinned or mis-pinned run

Standard library only, plus pyperf where the benchmarks need it.

    python3 -m unittest discover -s tests -v
"""
import argparse
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NBODY_DEV = os.path.join(ROOT, 'dev', 'nbody')
REPORT = os.path.join(ROOT, 'report')
RESULTS = os.path.join(ROOT, 'results')
for _p in (NBODY_DEV, REPORT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_txt_tables as ctt        # noqa: E402
import summarize_distribution as sd   # noqa: E402
import summarize_profiles as sp       # noqa: E402
import t0_stock                       # noqa: E402
import verify                         # noqa: E402

try:
    import pyperf  # noqa: F401
    HAVE_PYPERF = True
except ImportError:
    HAVE_PYPERF = False

STOCK, LANDED = verify._paths()
HAVE_STOCK = os.path.exists(STOCK)
BENCHMARKS = {b: os.path.join(ROOT, 'benchmarks', b, 'run_benchmark.py')
              for b in ('bm_nbody', 'bm_pyflate')}

_serial = [0]


def load_file(path, name, backend=None):
    """Import a source file as a fresh module, optionally under HWSW_BACKEND."""
    _serial[0] += 1
    modname = '_hwsw_test_%s_%d' % (name, _serial[0])
    loader = importlib.machinery.SourceFileLoader(modname, path)
    spec = importlib.util.spec_from_file_location(modname, path, loader=loader)
    mod = importlib.util.module_from_spec(spec)
    with environ(HWSW_BACKEND=backend):
        spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def environ(**values):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def fake_module(name, module):
    saved = sys.modules.get(name)
    sys.modules[name] = module
    try:
        yield module
    finally:
        if saved is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved


@contextlib.contextmanager
def argv(*args):
    saved = sys.argv
    sys.argv = list(args)
    try:
        yield
    finally:
        sys.argv = saved


def quiet():
    return contextlib.redirect_stdout(io.StringIO())


def flat(mod):
    out = []
    for r, v, m in mod.SYSTEM:
        out.extend(r)
        out.extend(v)
        out.append(m)
    return out


# ---------------------------------------------------------------------------
@unittest.skipUnless(HAVE_STOCK and HAVE_PYPERF,
                     'needs the stock bm_nbody source and pyperf')
class VerifyContracts(unittest.TestCase):

    def test_exactness_gates_the_exit_status(self):
        real = verify.compare

        def rounding_changed(label, *rest):
            ok, exact = real(label, *rest)
            return ok, exact and not label.strip().startswith('after')

        with quiet(), environ(HWSW_BACKEND=None):
            with argv('verify.py', '--steps', '50'):
                self.assertEqual(verify.main(), 0)
            verify.compare = rounding_changed
            try:
                with argv('verify.py', '--steps', '50'):
                    self.assertEqual(verify.main(), 1,
                                     'a tolerance-only pass was accepted')
            finally:
                verify.compare = real

    def test_missing_stock_reference_is_a_failure_not_a_skip(self):
        real = verify._paths
        verify._paths = lambda: (os.path.join(ROOT, 'no', 'stock.py'), LANDED)
        try:
            with quiet():
                self.assertFalse(verify.check_landed(20))
                self.assertFalse(verify.check_landed_n(20, 10))
        finally:
            verify._paths = real

    def test_python_kernel_is_checked_when_a_wheel_is_installed(self):
        # The course-VM failure: nbody_rs importable, HWSW_BACKEND unset.
        with fake_module('nbody_rs', types.ModuleType('nbody_rs')), \
                environ(HWSW_BACKEND=None), quiet():
            self.assertTrue(verify.check_landed_n(300, 10))


# ---------------------------------------------------------------------------
class _ReplaySystem:
    """Stand-in for nbody_rs.System that replays the stock Python kernel."""
    perturb = False

    def __init__(self, bodies):
        self.st = t0_stock.make_state()

    def offset_momentum(self, index):
        pass

    def advance(self, dt, n):
        t0_stock.advance(self.st, dt, n)

    def energy(self):
        return t0_stock.energy(self.st)

    def state(self):
        d = list(t0_stock.dump(self.st))
        if _ReplaySystem.perturb:
            d[7] *= 1 + 2 ** -52                       # one ulp, one component
        pos, vel, mass = [], [], []
        for i in range(len(d) // 7):
            pos += d[7 * i:7 * i + 3]
            vel += d[7 * i + 3:7 * i + 6]
            mass.append(d[7 * i + 6])
        return pos, vel, mass


class NbodyRsCheck(unittest.TestCase):

    def run_check(self, perturb, *args):
        stub = types.ModuleType('nbody_rs')
        stub.System = _ReplaySystem
        _ReplaySystem.perturb = perturb
        try:
            with fake_module('nbody_rs', stub):
                mod = load_file(os.path.join(NBODY_DEV, 'rs_check.py'), 'rs_check')
                mod.STEPS, mod.ROUNDS = 100, 1
                with argv('rs_check.py', *args), quiet():
                    return mod.main()
        finally:
            _ReplaySystem.perturb = False

    def test_identical_state_holds_the_exact_contract(self):
        self.assertEqual(self.run_check(False), 0)

    def test_one_ulp_breaks_the_exact_contract(self):
        self.assertEqual(self.run_check(True), 1)

    def test_tolerance_flag_moves_the_gate(self):
        self.assertEqual(self.run_check(True, '--tolerance'), 0)


# ---------------------------------------------------------------------------
@unittest.skipUnless(HAVE_PYPERF, 'the benchmarks import pyperf')
class BenchmarkBackend(unittest.TestCase):

    def test_native_metadata_hashes_the_compiled_extension(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        pkg = os.path.join(tmp, 'fakers')
        os.mkdir(pkg)
        stub = os.path.join(pkg, '__init__.py')
        with open(stub, 'w') as fh:
            fh.write('from .fakers import *\n')
        so = os.path.join(pkg, 'fakers' + importlib.machinery.EXTENSION_SUFFIXES[0])
        with open(so, 'wb') as fh:
            fh.write(b'compiled kernel')
        fake = types.ModuleType('fakers')
        fake.__file__, fake.__path__ = stub, [pkg]

        for bench, path in BENCHMARKS.items():
            with self.subTest(bench=bench):
                mod = load_file(path, bench, backend='python')
                runner = types.SimpleNamespace(metadata={})
                mod._backend_metadata(runner, fake, 'native')
                self.assertEqual(runner.metadata['hwsw_native_module'], so)
                self.assertEqual(runner.metadata['hwsw_native_sha256'],
                                 hashlib.sha256(b'compiled kernel').hexdigest())

    def test_backend_reaches_pyperf_workers(self):
        cases = ((None, ['HWSW_BACKEND']),
                 (['PATH'], ['PATH', 'HWSW_BACKEND']),
                 (['HWSW_BACKEND'], ['HWSW_BACKEND']))
        for bench, path in BENCHMARKS.items():
            mod = load_file(path, bench, backend='python')
            for existing, expected in cases:
                with self.subTest(bench=bench, existing=existing):
                    args = argparse.Namespace(inherit_environ=existing)
                    runner = types.SimpleNamespace(parse_args=lambda a=args: a)
                    self.assertIs(mod._propagate_backend(runner), args)
                    self.assertEqual(args.inherit_environ, expected)

    @unittest.skipUnless(HAVE_STOCK, 'needs the stock bm_nbody source')
    def test_native_mode_leaves_a_correct_advance_at_any_n(self):
        with fake_module('nbody_rs', types.ModuleType('nbody_rs')):
            landed = load_file(LANDED, 'bm_nbody_native', backend='native')
        self.assertIsNotNone(landed.nbody_rs)
        landed._configure(10)
        stock = load_file(STOCK, 'bm_nbody_stock')
        verify._scale_stock_module(stock, 10)
        for m in (stock, landed):
            m.offset_momentum(m.BODIES[m.DEFAULT_REFERENCE])
        self.assertEqual(flat(stock), flat(landed))
        stock.advance(0.01, 300)
        landed.advance(0.01, 300)
        self.assertEqual(flat(stock), flat(landed),
                         'native-mode advance() is stale for N > 5')


# ---------------------------------------------------------------------------
class DistributionSummary(unittest.TestCase):

    @staticmethod
    def workers(k, sd_between, sd_within, m=3, seed=7):
        rng = random.Random(seed)
        means = [rng.gauss(0, sd_between) for _ in range(k)]
        return [[rng.gauss(mu, sd_within) for _ in range(m)] for mu in means]

    def test_recovers_a_known_icc(self):
        between, within, icc = sd.variance_components(self.workers(4000, 3, 1))
        self.assertAlmostEqual(between ** 0.5, 3, delta=0.1)
        self.assertAlmostEqual(within ** 0.5, 1, delta=0.05)
        self.assertAlmostEqual(icc, 0.9, delta=0.02)

    def test_no_worker_effect_is_reported_as_zero(self):
        _, _, icc = sd.variance_components(self.workers(4000, 0, 1))
        self.assertLess(icc, 0.02)

    def test_quantiles(self):
        xs = list(range(1, 11))
        self.assertEqual((sd.quantile(xs, .25), sd.quantile(xs, .5),
                          sd.quantile(xs, .75)), (3.25, 5.5, 7.75))

    def test_calibration_runs_are_not_measurements(self):
        suite = {'metadata': {'hwsw_backend': 'python'}, 'benchmarks': [{'runs': [
            {'metadata': {}, 'warmups': [[1, 9.0]]},
            {'metadata': {}, 'values': [0.1, 0.2, 0.3]},
            {'metadata': {}, 'values': [0.2, 0.3, 0.4]}]}]}
        fd, path = tempfile.mkstemp(suffix='.json', dir=ROOT)
        self.addCleanup(os.remove, path)
        with os.fdopen(fd, 'w') as fh:
            json.dump(suite, fh)
        r = sd.summarize(path)
        self.assertEqual((r['workers'], r['values']), (2, 6))
        self.assertAlmostEqual(r['mean_ms'], 250.0)
        self.assertAlmostEqual(r['median_ms'], 250.0)
        self.assertEqual(r['backend'], 'python')


# ---------------------------------------------------------------------------
PERF_NBODY = os.path.join(RESULTS, 'perf_report_nbody_stock.txt')
FLAME_PYFLATE_OPT = os.path.join(RESULTS, 'pyspy_pyflate_opt_full.svg')


class ProfileTables(unittest.TestCase):

    @unittest.skipUnless(os.path.exists(PERF_NBODY), 'recorded profile absent')
    def test_perf_figures_the_nbody_report_quotes(self):
        rows, _ = sp.read_perf(PERF_NBODY)
        self.assertAlmostEqual(sum(r['self_pct'] for r in rows), 100.0, delta=0.5)
        (lists, floats) = sp.group_totals(rows, [
            ('list', r'^(list_|listiter_|PyNumber_AsSsize_t|PyLong_AsSsize_t)'),
            ('float', r'^(float_|PyFloat_)')])
        self.assertAlmostEqual(lists['self_pct'], 11.26, places=2)
        self.assertAlmostEqual(floats['self_pct'], 16.25, places=2)

    @unittest.skipUnless(os.path.exists(FLAME_PYFLATE_OPT), 'recorded profile absent')
    def test_flame_self_and_inclusive(self):
        rows, total = sp.read_flame(FLAME_PYFLATE_OPT)
        by_name = {r['name']: r for r in rows}
        bwt = by_name['bwt_reverse (run_benchmark.py)']
        self.assertEqual(total, 122)
        self.assertAlmostEqual(bwt['self_pct'], 13.11, places=2)
        self.assertAlmostEqual(bwt['inclusive_pct'], 38.52, places=2)
        self.assertTrue(all(r['inclusive_pct'] <= 100.0 + 1e-9 for r in rows))
        self.assertTrue(all(r['self_pct'] <= r['inclusive_pct'] + 1e-9 for r in rows))


# ---------------------------------------------------------------------------
class TextExportCheck(unittest.TestCase):
    TYP = ('#result-table(columns: 3,\n'
           '  table.header([*Row*], [*Runtime*], [*Added*]),\n'
           '  [alpha], [1.0 ms], [+1.0 ms],\n'
           '  [beta], [2.0 ms], [+2.0 ms],\n'
           '  [gamma], [3.0 ms], [+3.0 ms],\n'
           ')\n')

    def check(self, txt):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        typ, out = os.path.join(tmp, 'r.typ'), os.path.join(tmp, 'r.txt')
        with open(typ, 'w', encoding='utf-8') as fh:
            fh.write(self.TYP)
        with open(out, 'wb') as fh:
            fh.write(txt)
        return ctt.check_paths('sample', typ, out)

    def test_intact_table(self):
        self.assertEqual(self.check(
            b'Row   Runtime   Added\n'
            b'alpha   1.0 ms   +1.0 ms\n'
            b'beta    2.0 ms   +2.0 ms\n'
            b'gamma   3.0 ms   +3.0 ms\n'), [])

    def test_wrapped_row_is_cosmetic(self):
        self.assertEqual(self.check(
            b'alpha   1.0 ms   +1.0 ms\n'
            b'beta\n            2.0 ms   +2.0 ms\n'
            b'gamma   3.0 ms   +3.0 ms\n'), [])

    def test_values_shifted_one_row_are_rejected(self):
        # The pyflate ablation table as pdftotext once exported it.
        problems = self.check(
            b'alpha   1.0 ms\n'
            b'beta    2.0 ms   +1.0 ms\n'
            b'gamma   3.0 ms   +2.0 ms\n'
            b'                 +3.0 ms\n')
        self.assertTrue(any("'alpha'" in p for p in problems), problems)
        self.assertTrue(any("'beta'" in p for p in problems), problems)

    def test_invalid_utf8_is_rejected(self):
        problems = self.check(
            b'alpha 1.0 ms +1.0 ms\nbeta 2.0 ms +2.0 ms\ngamma 3.0 ms +3.0 ms\n'
            b'S = \xed\xa0\xb5\xed\xb1\x86\n')
        self.assertTrue(any('UTF-8' in p for p in problems), problems)


# ---------------------------------------------------------------------------
def _bash_with_python3():
    bash = shutil.which('bash')
    if not bash:
        return None
    try:
        ok = subprocess.run([bash, '-c', 'python3 -c "import json"'],
                            capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None
    return bash if ok else None


BASH = _bash_with_python3()


@unittest.skipUnless(BASH, 'needs bash with python3 on PATH')
class RunnerAssertions(unittest.TestCase):

    def assert_backend(self, metadata, want, cpu=''):
        fd, path = tempfile.mkstemp(suffix='.json')
        self.addCleanup(os.remove, path)
        with os.fdopen(fd, 'w') as fh:
            json.dump({'metadata': metadata, 'benchmarks': [{'runs': []}]}, fh)
        script = 'BENCH=nbody; . tools/runner_common.sh; CPU="$3"; assert_backend "$1" "$2"'
        r = subprocess.run([BASH, '-c', script, '_', path, want, cpu], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def test_honoured_request_passes(self):
        rc, out = self.assert_backend({'hwsw_backend': 'native',
                                       'hwsw_backend_requested': 'native',
                                       'cpu_affinity': '0'}, 'native', '0')
        self.assertEqual(rc, 0, out)

    def test_wrong_backend_fails(self):
        rc, out = self.assert_backend({'hwsw_backend': 'python',
                                       'hwsw_backend_requested': 'python'}, 'native')
        self.assertNotEqual(rc, 0)
        self.assertIn('MISMATCH', out)

    def test_unpinned_workers_fail_even_on_the_right_path(self):
        rc, out = self.assert_backend({'hwsw_backend': 'native',
                                       'hwsw_backend_requested': 'auto'}, 'native')
        self.assertNotEqual(rc, 0)
        self.assertIn('NOT PINNED', out)

    def test_wrong_cpu_fails(self):
        rc, out = self.assert_backend({'hwsw_backend': 'python',
                                       'hwsw_backend_requested': 'python',
                                       'cpu_affinity': '3'}, 'python', '0')
        self.assertNotEqual(rc, 0)
        self.assertIn('AFFINITY', out)

    def test_stock_run_without_backend_metadata(self):
        rc, out = self.assert_backend({'cpu_affinity': '0'}, '-', '0')
        self.assertEqual(rc, 0, out)


if __name__ == '__main__':
    unittest.main()
