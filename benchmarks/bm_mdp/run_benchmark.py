"""Solve a Gen-1 Pokemon battle as a Markov decision process.

Optimized version of the pyperformance 1.14.0 `mdp` benchmark.  It computes
the identical result by the identical algorithm: the same state graph, the
same exact transition probabilities, the same Gauss-Seidel interval value
iteration in the same topological order, the same freeze rule, and the same
111 sweeps.  Verified bit-for-bit -- not just the asserted root value, but
all 4823 states x 2 bounds and all 22418 transition probabilities (see
dev/mdp/verify.py).

Three changes, none of which alters what is computed:

1.  getCritDist is memoized.  It is a pure function, called 3659 times per
    run with only 3 distinct argument tuples (stats are constant during a
    battle; only HP changes).  The cache is per-run, so every measured
    iteration does exactly the work stock does.

2.  fractions.Fraction is replaced by exact fixed-denominator integers.
    Every probability here is a rational whose denominator divides a
    statically known constant:
        DMG_DEN  = 512 * 39 = 19968   (one attack outcome)
        MULT_DEN = 260                (the enemy's move mixture)
        DEN      = DMG_DEN * MULT_DEN = 5191680 < 2**23
    so numerators are single-digit CPython ints and no gcd is ever needed.
    This is exact, not approximate: Fraction.__float__ is numerator /
    denominator on the reduced pair and int division is correctly rounded,
    so num / DEN yields the identical double.

3.  States are renumbered to dense integers after topoSort and the graph is
    flattened to CSR arrays (kind/row/col/prb/lo/hi/frz).  Stock addresses
    every value by a tuple of nested namedtuples, and CPython does not cache
    tuple hashes, so the sweep loop was re-hashing deep structures roughly
    5 million times per run.  The CSR sweep is the same arithmetic in the
    same order over list indices.

NOTE for anyone porting the sweep: accumulate naively left-to-right, do not
reorder edges, and do not parallelize across nodes.  Node-level parallelism
turns Gauss-Seidel into Jacobi, which needs 369 sweeps instead of 111 and
lands on a different answer.
"""
import collections
import functools

import pyperf

DMG_DEN = 512 * 39          # 19968   - denominator of a single-attack outcome
MULT_DEN = 260              # denominator of the enemy's move mixture
DEN = DMG_DEN * MULT_DEN    # 5191680 - denominator of a joint outcome

CHANCE = 1                  # node kinds: expectation node ...
CHOICE = 0                  # ... and player-choice (max) node


def topoSort(roots, getParents):
    """Return a topological sorting of nodes in a graph.

    roots - list of root nodes to search from
    getParents - function which returns the parents of a given node
    """

    results = []
    visited = set()

    # Use iterative version to avoid stack limits for large datasets
    stack = [(node, 0) for node in roots]
    while stack:
        current, state = stack.pop()
        if state == 0:
            # before recursing
            if current not in visited:
                visited.add(current)
                stack.append((current, 1))
                stack.extend((parent, 0) for parent in getParents(current))
        else:
            # after recursing
            results.append(current)
    return results


def getDamages(L, A, D, B, stab, te):
    x = (2 * L) // 5
    x = ((x + 2) * A * B) // (D * 50) + 2
    if stab:
        x += x // 2
    x = int(x * te)
    return [(x * z) // 255 for z in range(217, 256)]


@functools.lru_cache(maxsize=None)
def getCritDist(L, pnum, pden, A1, A2, D1, D2, B, stab, te):
    """Damage distribution as integer numerators over DMG_DEN (exact)."""
    if pnum > pden:                      # min(p, 1)
        pnum = pden = 1
    norm = getDamages(L, A1, D1, B, stab, te)
    crit = getDamages(L * 2, A2, D2, B, stab, te)

    # (1 - p) / len(norm) and p / len(norm), as numerators over DMG_DEN
    scale, rem = divmod(DMG_DEN, pden * len(norm))
    assert rem == 0

    dist = collections.defaultdict(int)
    for mult, vals in ((pden - pnum) * scale, norm), (pnum * scale, crit):
        for x in vals:
            dist[x] += mult
    return dist


def plus12(x):
    return x + x // 8


stats_t = collections.namedtuple('stats_t', ['atk', 'df', 'speed', 'spec'])
NOMODS = stats_t(0, 0, 0, 0)


fixeddata_t = collections.namedtuple(
    'fixeddata_t', ['maxhp', 'stats', 'lvl', 'badges', 'basespeed'])
halfstate_t = collections.namedtuple(
    'halfstate_t', ['fixed', 'hp', 'status', 'statmods', 'stats'])


def applyHPChange(hstate, change):
    hp = min(hstate.fixed.maxhp, max(0, hstate.hp + change))
    return hstate._replace(hp=hp)


def applyBadgeBoosts(badges, stats):
    return stats_t(*[(plus12(x) if b else x) for x, b in zip(stats, badges)])


attack_stats_t = collections.namedtuple(
    'attack_stats_t', ['power', 'isspec', 'stab', 'te', 'crit'])
attack_data = {
    'Ember': attack_stats_t(40, True, True, 0.5, False),
    'Dig': attack_stats_t(100, False, False, 1, False),
    'Slash': attack_stats_t(70, False, False, 1, True),
    'Water Gun': attack_stats_t(40, True, True, 2, False),
    'Bubblebeam': attack_stats_t(65, True, True, 2, False),
}


def _applyActionSide1(state, act):
    """Outcome distribution as integer numerators over DMG_DEN."""
    me, them, extra = state

    if act == 'Super Potion':
        me = applyHPChange(me, 50)
        return {(me, them, extra): DMG_DEN}

    mdata = attack_data[act]
    aind = 3 if mdata.isspec else 0
    dind = 3 if mdata.isspec else 1
    pdiv = 64 if mdata.crit else 512
    dmg_dist = getCritDist(me.fixed.lvl, me.fixed.basespeed, pdiv,
                           me.stats[aind], me.fixed.stats[aind],
                           them.stats[dind], them.fixed.stats[dind],
                           mdata.power, mdata.stab, mdata.te)

    dist = collections.defaultdict(int)
    for dmg, p in dmg_dist.items():
        them2 = applyHPChange(them, -dmg)
        dist[me, them2, extra] += p
    return dist


def _applyAction(state, side, act):
    if side == 0:
        return _applyActionSide1(state, act)
    else:
        me, them, extra = state
        dist = _applyActionSide1((them, me, extra), act)
        return {(k[1], k[0], k[2]): v for k, v in dist.items()}


class Battle(object):

    def __init__(self):
        self.successors = {}
        self.win = 4, True
        self.loss = 4, False
        # per-run cache: every measured iteration does the same work
        getCritDist.cache_clear()

    def _getSuccessorsA(self, statep):
        st, state = statep
        for action in ['Dig', 'Super Potion']:
            yield (1, state, action)

    def _applyActionPair(self, state, side1, act1, side2, act2, dist, pmult):
        win, loss = self.win, self.loss
        for newstate, p in _applyAction(state, side1, act1).items():
            if newstate[0].hp == 0:
                newstatep = loss
            elif newstate[1].hp == 0:
                newstatep = win
            else:
                newstatep = 2, newstate, side2, act2
            dist[newstatep] += p * pmult

    def _getSuccessorsB(self, statep):
        st, state, action = statep
        dist = collections.defaultdict(int)
        # 64/130 -> 128/260 and 66/130 -> 132/260, over MULT_DEN
        for eact, p in (('Water Gun', 128), ('Bubblebeam', 132)):
            priority1 = (state[0].stats.speed
                         + 10000 * (action == 'Super Potion'))
            priority2 = state[1].stats.speed + 10000 * (action == 'X Defend')

            if priority1 > priority2:
                self._applyActionPair(state, 0, action, 1, eact, dist, p)
            elif priority1 < priority2:
                self._applyActionPair(state, 1, eact, 0, action, dist, p)
            else:
                h = p >> 1
                self._applyActionPair(state, 0, action, 1, eact, dist, h)
                self._applyActionPair(state, 1, eact, 0, action, dist, h)

        return {k: n / DEN for k, n in dist.items() if n > 0}

    def _getSuccessorsC(self, statep):
        st, state, side, action = statep
        dist = collections.defaultdict(int)
        win, loss = self.win, self.loss
        for newstate, p in _applyAction(state, side, action).items():
            if newstate[0].hp == 0:
                newstatep = loss
            elif newstate[1].hp == 0:
                newstatep = win
            else:
                newstatep = 0, newstate
            dist[newstatep] += p
        return {k: n / DMG_DEN for k, n in dist.items() if n > 0}

    def getSuccessors(self, statep):
        try:
            return self.successors[statep]
        except KeyError:
            st = statep[0]
        if st == 0:
            result = list(self._getSuccessorsA(statep))
        else:
            if st == 1:
                dist = self._getSuccessorsB(statep)
            elif st == 2:
                dist = self._getSuccessorsC(statep)
            result = sorted(dist.items(), key=lambda t: (-t[1], t[0]))
        self.successors[statep] = result
        return result

    def getSuccessorsList(self, statep):
        if statep[0] == 4:
            return []
        temp = self.getSuccessors(statep)
        if statep[0] != 0:
            temp = list(zip(*temp))[0] if temp else []
        return temp

    def _buildCSR(self, initial_statep):
        """topoSort the graph, then renumber states to dense integers and
        flatten the successor lists into CSR arrays.

        Node i owns col[row[i]:row[i+1]] and prb[row[i]:row[i+1]].  The node
        order is exactly the topological order stock sweeps in, so the value
        iteration below is the same Gauss-Seidel pass over the same nodes in
        the same sequence.
        """
        stateps = topoSort([initial_statep], self.getSuccessorsList)
        succs = self.successors
        n = len(stateps)
        idx = {}
        for i, sp in enumerate(stateps):
            idx[sp] = i

        kind = bytearray(n)
        row = [0] * (n + 1)
        lo = [0.0] * n
        hi = [1.0] * n
        frz = bytearray(n)
        col = []
        prb = []

        for i, sp in enumerate(stateps):
            st = sp[0]
            if st == 4:
                # terminal: win == (4, True) -> [1, 1], loss -> [0, 0]
                lo[i] = hi[i] = 1.0 if sp[1] else 0.0
                frz[i] = 1
            elif st == 0:
                kind[i] = CHOICE
                for sp2 in succs[sp]:
                    col.append(idx[sp2])
                    prb.append(0.0)
            else:
                kind[i] = CHANCE
                for sp2, p in succs[sp]:
                    col.append(idx[sp2])
                    prb.append(p)
            row[i + 1] = len(col)

        order = [i for i in range(n) if not frz[i]]
        return kind, row, col, prb, lo, hi, frz, order, idx[initial_statep]

    def evaluate(self, tolerance=0.15):
        badges = 1, 0, 0, 0

        starfixed = fixeddata_t(59, stats_t(40, 44, 56, 50), 11, NOMODS, 115)
        starhalf = halfstate_t(starfixed, 59, 0, NOMODS,
                               stats_t(40, 44, 56, 50))
        charfixed = fixeddata_t(63, stats_t(39, 34, 46, 38), 26, badges, 65)
        charhalf = halfstate_t(charfixed, 63, 0, NOMODS, applyBadgeBoosts(
            badges, stats_t(39, 34, 46, 38)))
        initial_state = charhalf, starhalf, 0
        initial_statep = 0, initial_state

        kind, row, col, prb, lo, hi, frz, order, root = \
            self._buildCSR(initial_statep)

        self.itercount = 0
        while hi[root] - lo[root] > tolerance:
            self.itercount += 1
            newly_frozen = False

            for i in order:
                s = row[i]
                e = row[i + 1]
                if kind[i]:
                    # expectation node: accumulate left-to-right, in the
                    # edge order the model was built in
                    a = 0.0
                    c = 0.0
                    for j in range(s, e):
                        k = col[j]
                        p = prb[j]
                        a += lo[k] * p
                        c += hi[k] * p
                else:
                    # choice node: max over the successors
                    k = col[s]
                    a = lo[k]
                    c = hi[k]
                    for j in range(s + 1, e):
                        k = col[j]
                        v = lo[k]
                        if v > a:
                            a = v
                        v = hi[k]
                        if v > c:
                            c = v

                if a >= c:
                    a = c = (a + c) / 2
                    frz[i] = 1
                    newly_frozen = True
                lo[i] = a
                hi[i] = c

            if newly_frozen:
                # frozen states never change again: drop them from the sweep
                order = [i for i in order if not frz[i]]

        return (hi[root] + lo[root]) / 2


def bench_mdp(loops):
    expected = 0.89873589887
    max_diff = 1e-6
    range_it = range(loops)

    t0 = pyperf.perf_counter()
    for _ in range_it:
        result = Battle().evaluate(0.192)
    dt = pyperf.perf_counter() - t0

    if abs(result - expected) > max_diff:
        raise Exception("invalid result: got %s, expected %s "
                        "(diff: %s, max diff: %s)"
                        % (result, expected, result - expected, max_diff))
    return dt


if __name__ == "__main__":
    runner = pyperf.Runner()
    runner.metadata['description'] = "MDP benchmark"
    runner.bench_time_func('mdp', bench_mdp)
