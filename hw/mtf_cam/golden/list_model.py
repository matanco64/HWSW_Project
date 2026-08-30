"""Emulation model for mtf_cam (the pyuvm predictor), written independently of pyflate.

MTF list: initialised as the ascending list of used byte values; a symbol s >= 2 selects rank
r = s - 1 (bzip2 codes MTF value v >= 1 as symbol v + 1; value 0 is always a run, so rank 0 never
occurs), emits list[r] and moves it to the front (ranks 0..r-1 shift down by one).
Run expander: RUNA (0) / RUNB (1) accumulate a bijective base-2 count
    run += (1 << k) * (1 + s)   for the k-th consecutive run symbol (k = 0, 1, ...)
and, at the first non-run symbol (an MTF symbol or EOB), emit `run` copies of list[0].
EOB (= alphabet - 1) ends the block. Output = the L-vector bytes.

Cycle model (PRD K3), the assumptions the PRD states and uArch confirms:
  * symbol side: one symbol accepted per cycle (MTF list update, or run accumulate); it produces
    an output *item* — an MTF byte, or, at the symbol that terminates a run group, the run item
    (n bytes) followed by that symbol's own item — into an item FIFO of depth D items;
    the symbol side stalls (s_sym.tready = 0) when the FIFO is full;
  * drain side: a byte item takes 1 cycle, a run item ceil(n / W) cycles at W bytes per cycle;
  * output bytes are packed into W-byte beats (TKEEP partial only on the last beat); the packer
    adds no cycles; `m_l.tready` = 1 and `s_sym.tvalid` = 1 throughout;
  * init = N_USED cycles before the first symbol; DONE one cycle after the last beat.
  Lower bound = max(symbols, drain cycles); D = 0 means no FIFO (fully serialised).
"""


RUN_MAX = 1 << 20          # PRD-F3/F10: n <= 2^20 (bzip2 blocks are <= 900 kB), at most 20 run symbols


def expand(symbols, used, alphabet):
    """Functional model. Returns (l_bytes, events); events: ('mtf', rank, byte) | ('run', n, byte) | ('eob',)."""
    lst = [b for b in range(256) if used[b]]
    eob = alphabet - 1
    out = bytearray()
    events = []
    run = 0
    k = 0
    for s in symbols:
        if s <= 1:
            run += (1 << k) * (1 + s)
            k += 1
            if run > RUN_MAX:
                raise ValueError("ERR_RUN: run length %d > 2^20 at run symbol %d of the group" % (run, k))
            continue
        if run:
            out.extend(bytes([lst[0]]) * run)
            events.append(("run", run, lst[0]))
            run = 0
            k = 0
        if s == eob:
            events.append(("eob",))
            break
        if s >= alphabet:
            raise ValueError("ERR_RANK: symbol %d >= ALPHABET %d" % (s, alphabet))
        r = s - 1
        b = lst.pop(r)
        lst.insert(0, b)
        out.append(b)
        events.append(("mtf", r, b))
    return bytes(out), events


def cycles(symbols, used, alphabet, W=8, D=0):
    """Cycle model (docstring above). Returns total cycles doorbell -> DONE."""
    n_used = sum(used)
    eob = alphabet - 1
    items_at = []                       # per accepted symbol: list of drain occupancies it produces
    run = 0
    k = 0
    for s in symbols:
        if s <= 1:
            run += (1 << k) * (1 + s)
            k += 1
            items_at.append([])
            continue
        its = []
        if run:
            its.append(-(-run // W))
            run = 0
            k = 0
        if s != eob:
            its.append(1)
        items_at.append(its)
        if s == eob:
            break
    t = n_used
    q = []
    i_in = 0
    busy_until = t
    n = len(items_at)
    while i_in < n or q or t < busy_until:
        if t >= busy_until and q:                       # drain side starts the next item
            busy_until = t + q.pop(0)
        if i_in < n:                                    # symbol side accepts one symbol per cycle
            need = len(items_at[i_in])
            if D == 0:
                if not q and t >= busy_until:
                    q.extend(items_at[i_in]); i_in += 1
                    if q:
                        busy_until = t + q.pop(0)
            elif len(q) + need <= D:
                q.extend(items_at[i_in]); i_in += 1
        t += 1
    return max(t, busy_until) + 1
