"""T1 - memoize getCritDist + micro cleanups.  Bit-identical trajectory.

Changes vs T0 (all constant-factor, none algorithmic):

  1. getCritDist is a *pure* function called 3659 times with only 3 distinct
     argument tuples (measured, see analyze.py crit).  functools.lru_cache
     turns 3656 of those calls into a dict hit.  The distributions are still
     computed -- just once each.

  2. The sweep loop looks the successor list up ONCE per node instead of
     twice (stock calls self.getSuccessors(sp) separately for dmin and for
     dmax).  Each call hashed a deeply nested namedtuple key, so this halves
     the state-key hashing in the iteration phase.

  3. Active list instead of `if sp in frozen: continue`.  Stock pays one deep
     tuple hash per node per sweep (4823 x 111 = 535k hashes) just to skip
     nodes it already froze.  Freezing only ever happens during sweep 1
     (measured), so the list is rebuilt at most twice.

  4. dmin / dmax / successors bound to locals in the hot loop.

The update order, the arithmetic and the freeze rule are untouched, so the
float trajectory -- and therefore the sweep count and the result -- are
bit-identical to stock.
"""
import collections
import functools
import time
from collections import defaultdict
from fractions import Fraction

TOLERANCE = 0.192
EXPECTED = 0.89873589887


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
def getCritDist(L, p, A1, A2, D1, D2, B, stab, te):
    p = min(p, Fraction(1))
    norm = getDamages(L, A1, D1, B, stab, te)
    crit = getDamages(L * 2, A2, D2, B, stab, te)

    dist = defaultdict(Fraction)
    for mult, vals in zip([1 - p, p], [norm, crit]):
        mult /= len(vals)
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
    me, them, extra = state

    if act == 'Super Potion':
        me = applyHPChange(me, 50)
        return {(me, them, extra): Fraction(1)}

    mdata = attack_data[act]
    aind = 3 if mdata.isspec else 0
    dind = 3 if mdata.isspec else 1
    pdiv = 64 if mdata.crit else 512
    dmg_dist = getCritDist(me.fixed.lvl, Fraction(me.fixed.basespeed, pdiv),
                           me.stats[aind], me.fixed.stats[aind],
                           them.stats[dind], them.fixed.stats[dind],
                           mdata.power, mdata.stab, mdata.te)

    dist = defaultdict(Fraction)
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
        self.min = defaultdict(float)
        self.max = defaultdict(lambda: 1.0)
        self.frozen = set()

        self.win = 4, True
        self.loss = 4, False
        self.max[self.loss] = 0.0
        self.min[self.win] = 1.0
        self.frozen.update([self.win, self.loss])

    def _getSuccessorsA(self, statep):
        st, state = statep
        for action in ['Dig', 'Super Potion']:
            yield (1, state, action)

    def _applyActionPair(self, state, side1, act1, side2, act2, dist, pmult):
        for newstate, p in _applyAction(state, side1, act1).items():
            if newstate[0].hp == 0:
                newstatep = self.loss
            elif newstate[1].hp == 0:
                newstatep = self.win
            else:
                newstatep = 2, newstate, side2, act2
            dist[newstatep] += p * pmult

    def _getSuccessorsB(self, statep):
        st, state, action = statep
        dist = defaultdict(Fraction)
        for eact, p in [('Water Gun', Fraction(64, 130)),
                        ('Bubblebeam', Fraction(66, 130))]:
            priority1 = (state[0].stats.speed
                         + 10000 * (action == 'Super Potion'))
            priority2 = state[1].stats.speed + 10000 * (action == 'X Defend')

            if priority1 > priority2:
                self._applyActionPair(state, 0, action, 1, eact, dist, p)
            elif priority1 < priority2:
                self._applyActionPair(state, 1, eact, 0, action, dist, p)
            else:
                self._applyActionPair(state, 0, action, 1, eact, dist, p / 2)
                self._applyActionPair(state, 1, eact, 0, action, dist, p / 2)

        return {k: float(p) for k, p in dist.items() if p > 0}

    def _getSuccessorsC(self, statep):
        st, state, side, action = statep
        dist = defaultdict(Fraction)
        for newstate, p in _applyAction(state, side, action).items():
            if newstate[0].hp == 0:
                newstatep = self.loss
            elif newstate[1].hp == 0:
                newstatep = self.win
            else:
                newstatep = 0, newstate
            dist[newstatep] += p
        return {k: float(p) for k, p in dist.items() if p > 0}

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

    def evaluate(self, tolerance=0.15):
        root = self.initial()
        dmin, dmax, frozen = self.min, self.max, self.frozen
        succs = self.successors
        stateps = topoSort([root], self.getSuccessorsList)

        active = [sp for sp in stateps if sp not in frozen]
        itercount = 0
        while dmax[root] - dmin[root] > tolerance:
            itercount += 1
            newly_frozen = False
            for sp in active:
                succ = succs[sp]
                if sp[0] == 0:
                    a = max(dmin[s] for s in succ)
                    b = max(dmax[s] for s in succ)
                else:
                    a = sum(dmin[s] * p for s, p in succ)
                    b = sum(dmax[s] * p for s, p in succ)
                if a >= b:
                    a = b = (a + b) / 2
                    frozen.add(sp)
                    newly_frozen = True
                dmin[sp] = a
                dmax[sp] = b
            if newly_frozen:
                active = [sp for sp in active if sp not in frozen]
        self.itercount = itercount
        return (dmax[root] + dmin[root]) / 2


def solve(tolerance=TOLERANCE):
    getCritDist.cache_clear()
    b = Battle()
    root = b.initial()
    dmin, dmax, frozen = b.min, b.max, b.frozen
    succs = b.successors

    t0 = time.perf_counter()
    stateps = topoSort([root], b.getSuccessorsList)
    t1 = time.perf_counter()

    active = [sp for sp in stateps if sp not in frozen]
    itercount = 0
    while dmax[root] - dmin[root] > tolerance:
        itercount += 1
        newly_frozen = False
        for sp in active:
            succ = succs[sp]
            if sp[0] == 0:
                a = max(dmin[s] for s in succ)
                b2 = max(dmax[s] for s in succ)
            else:
                a = sum(dmin[s] * p for s, p in succ)
                b2 = sum(dmax[s] * p for s, p in succ)
            if a >= b2:
                a = b2 = (a + b2) / 2
                frozen.add(sp)
                newly_frozen = True
            dmin[sp] = a
            dmax[sp] = b2
        if newly_frozen:
            active = [sp for sp in active if sp not in frozen]
    t2 = time.perf_counter()
    return (dmax[root] + dmin[root]) / 2, itercount, t1 - t0, t2 - t1


def run(tolerance=TOLERANCE):
    getCritDist.cache_clear()
    return Battle().evaluate(tolerance)


if __name__ == '__main__':
    r, n, tb, ti = solve()
    print("result=%.12f sweeps=%d build=%.3fs iter=%.3fs" % (r, n, tb, ti))
