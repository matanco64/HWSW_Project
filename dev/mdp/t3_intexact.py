"""T3 - exact fixed-denominator integer arithmetic instead of fractions.Fraction.

STILL EXACT.  Not an approximation: every probability in this benchmark is a
rational with a denominator that divides a small, statically known constant,
so we can carry plain Python ints as numerators over a fixed denominator and
never need a gcd.

  * getCritDist works over DMG_DEN = 512 * 39 = 19968.
        p        = basespeed / pdiv,  pdiv in {64, 512}, clamped at 1
        mult     = (1 - p) / 39  and  p / 39
        both are integers over DMG_DEN because DMG_DEN % (pdiv * 39) == 0.
  * the enemy-move mixture uses MULT_DEN = 260  (64/130 -> 128/260,
    66/130 -> 132/260, and their halves 64/260, 66/260).
  * a joint (my move, enemy move) outcome is a product of one of each, so it
    is an integer over DEN = DMG_DEN * MULT_DEN = 5,191,680 < 2**23.

Every numerator that appears is < 2**23, i.e. a single-digit CPython int, so
the adds and multiplies are the cheapest arithmetic the interpreter has.

What this removes versus stock (measured in the earlier profile): ~677k
math.gcd calls, ~382k Fraction._from_coprime_ints constructions and ~360k
Fraction.__add__ allocations.

Exactness of the hand-off to float: Fraction.__float__ is numerator /
denominator on the *reduced* pair, and int.__truediv__ is correctly rounded,
so num / DEN produces the identical double as float(Fraction(num, DEN)).
verify.py checks this edge-by-edge against the Fraction build.
"""
import collections
import functools
import time

import t2_csr as T2

TOLERANCE = 0.192
EXPECTED = 0.89873589887

DMG_DEN = 512 * 39          # 19968  - denominator of a single-attack outcome
MULT_DEN = 260              # denominator of the enemy's move mixture
DEN = DMG_DEN * MULT_DEN    # 5191680 - denominator of a joint outcome


def topoSort(roots, getParents):
    results = []
    visited = set()
    stack = [(node, 0) for node in roots]
    while stack:
        current, state = stack.pop()
        if state == 0:
            if current not in visited:
                visited.add(current)
                stack.append((current, 1))
                stack.extend((parent, 0) for parent in getParents(current))
        else:
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

    scale, rem = divmod(DMG_DEN, pden * len(norm))
    assert rem == 0 and len(norm) == len(crit)
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

    def _getSuccessorsA(self, statep):
        st, state = statep
        for action in ['Dig', 'Super Potion']:
            yield (1, state, action)

    def _applyActionPair(self, state, side1, act1, side2, act2, dist, pmult):
        loss = self.loss
        win = self.win
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
        # 64/130 -> 128/260, 66/130 -> 132/260 (halves: 64/260, 66/260)
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
        loss = self.loss
        win = self.win
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

    def initial(self):
        badges = 1, 0, 0, 0
        starfixed = fixeddata_t(59, stats_t(40, 44, 56, 50), 11, NOMODS, 115)
        starhalf = halfstate_t(starfixed, 59, 0, NOMODS,
                               stats_t(40, 44, 56, 50))
        charfixed = fixeddata_t(63, stats_t(39, 34, 46, 38), 26, badges, 65)
        charhalf = halfstate_t(charfixed, 63, 0, NOMODS,
                               applyBadgeBoosts(badges,
                                                stats_t(39, 34, 46, 38)))
        return 0, (charhalf, starhalf, 0)


def build_csr():
    """Same CSR object as T2, built without a single Fraction."""
    getCritDist.cache_clear()
    b = Battle()
    root = b.initial()
    stateps = topoSort([root], b.getSuccessorsList)
    succs = b.successors

    n = len(stateps)
    idx = {}
    for i, sp in enumerate(stateps):
        idx[sp] = i

    g = T2.CSR()
    g.n = n
    g.stateps = stateps
    g.root = idx[root]
    g.kind = bytearray(n)
    g.row = [0] * (n + 1)
    g.lo = [0.0] * n
    g.hi = [1.0] * n
    g.frz = bytearray(n)
    col = []
    prb = []
    for i, sp in enumerate(stateps):
        st = sp[0]
        if st == 4:
            g.lo[i] = g.hi[i] = 1.0 if sp[1] else 0.0
            g.frz[i] = 1
        elif st == 0:
            for sp2 in succs[sp]:
                col.append(idx[sp2])
                prb.append(0.0)
        else:
            g.kind[i] = T2.CHANCE
            for sp2, p in succs[sp]:
                col.append(idx[sp2])
                prb.append(p)
        g.row[i + 1] = len(col)
    g.col = col
    g.prb = prb
    g.order = [i for i in range(n) if not g.frz[i]]
    return g


def solve(tolerance=TOLERANCE):
    t0 = time.perf_counter()
    g = build_csr()
    t1 = time.perf_counter()
    r, it = T2.sweep_flat(g, tolerance)
    t2 = time.perf_counter()
    return r, it, t1 - t0, t2 - t1


def run(tolerance=TOLERANCE):
    return solve(tolerance)[0]


if __name__ == '__main__':
    r, n, tb, ti = solve()
    print("result=%.12f sweeps=%d build=%.3fs iter=%.3fs" % (r, n, tb, ti))
