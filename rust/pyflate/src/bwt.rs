//! EXPERIMENT (not shipped): inverse BWT and RLE4 in Rust.
//!
//! Every variant reproduces the Python `bwt_reverse` exactly:
//!
//! ```python
//! T = bucket_pointers(L)          # T[bucket slot of position i] = i
//! for k in range(n):
//!     end = T[end]
//!     out[k] = L[end]
//! ```
//!
//! i.e. `out[k] = L[T^(k+1)(end)]`.  That definition holds even when `T` is
//! several cycles (periodic input, the "STRANGENESS WARNING" in the Python),
//! because it never assumes the chain returns to `end`.

/// Bucket starts: `base[s]` = number of bytes in `l` smaller than `s`.
///
/// Four interleaved histograms: `L` is full of runs, and a single counter
/// array makes every repeated byte wait for the previous increment of the
/// same slot (3.5x slower on the benchmark block).
fn bucket_starts(l: &[u8]) -> [u32; 256] {
    let mut c = [[0u32; 256]; 4];
    let chunks = l.chunks_exact(4);
    for &s in chunks.remainder() {
        c[0][s as usize] += 1;
    }
    for w in chunks {
        c[0][w[0] as usize] += 1;
        c[1][w[1] as usize] += 1;
        c[2][w[2] as usize] += 1;
        c[3][w[3] as usize] += 1;
    }
    let mut base = [0u32; 256];
    let mut total = 0u32;
    for s in 0..256 {
        base[s] = total;
        total += c[0][s] + c[1][s] + c[2][s] + c[3][s];
    }
    base
}

/// Variant 1: literal port.  Two dependent random loads per output byte
/// (`T[end]`, then `L[end]`).
pub fn naive(l: &[u8], mut end: usize) -> Vec<u8> {
    let n = l.len();
    let mut base = bucket_starts(l);
    let mut t = vec![0u32; n];
    for (i, &s) in l.iter().enumerate() {
        let b = &mut base[s as usize];
        t[*b as usize] = i as u32;
        *b += 1;
    }
    let mut out = vec![0u8; n];
    for o in out.iter_mut() {
        end = t[end] as usize;
        *o = l[end];
    }
    out
}

/// Variant 2: bzip2's packing.  `p[slot] = (i << 8) | L[i]`, so one load
/// yields both the next position and the byte to emit.  Positions need 24
/// bits; a bzip2 block is at most 900,000 bytes.
pub fn packed(l: &[u8], end: usize) -> Vec<u8> {
    let n = l.len();
    let mut base = bucket_starts(l);
    let mut p = vec![0u32; n];
    for (i, &s) in l.iter().enumerate() {
        let b = &mut base[s as usize];
        p[*b as usize] = ((i as u32) << 8) | s as u32;
        *b += 1;
    }
    let mut out = vec![0u8; n];
    let mut x = end as u32;
    for o in out.iter_mut() {
        let v = p[x as usize];
        *o = v as u8;
        x = v >> 8;
    }
    out
}

/// Variant 3: two chains meeting in the middle.
///
/// Forward: `x <- T[x]` emits `out[0], out[1], ...` (as in `packed`).
/// Backward: with `LF = T^-1` (built in the same pass: `LF[i]` is the slot
/// `i` was placed in), `out[n-1-k] = L[LF^k(end)]`, since
/// `T^(n-k)(end) = LF^k(T^n(end))` and `T^n = id` for any permutation whose
/// cycle lengths divide n -- which every cycle of a BWT permutation does.
/// The two load chains are independent, so the core overlaps their misses.
pub fn two_chain(l: &[u8], end: usize) -> Vec<u8> {
    let n = l.len();
    if n == 0 {
        return Vec::new();
    }
    let mut base = bucket_starts(l);
    let mut p = vec![0u32; n]; // forward:  p[slot] = (i << 8) | L[i]
    let mut q = vec![0u32; n]; // backward: q[i]    = (slot << 8) | L[i]
    for (i, &s) in l.iter().enumerate() {
        let b = &mut base[s as usize];
        p[*b as usize] = ((i as u32) << 8) | s as u32;
        q[i] = (*b << 8) | s as u32;
        *b += 1;
    }
    let mut out = vec![0u8; n];
    let half = n / 2;
    let mut xf = end as u32; // forward cursor
    let mut xb = end as u32; // backward cursor
    // Forward fills out[0..half), backward fills out[half..n) from the top.
    let mut lo = 0usize;
    let mut hi = n;
    while lo < half {
        let vf = p[xf as usize];
        let vb = q[xb as usize];
        out[lo] = vf as u8;
        xf = vf >> 8;
        hi -= 1;
        out[hi] = vb as u8;
        xb = vb >> 8;
        lo += 1;
    }
    // Odd n: one byte left in the middle, finish it on the backward chain.
    while hi > lo {
        let vb = q[xb as usize];
        hi -= 1;
        out[hi] = vb as u8;
        xb = vb >> 8;
    }
    out
}

/// bzip2's final run-length step, same semantics as the Python
/// `rle4_expand`: four equal bytes are followed by a count byte (0..255)
/// of further copies; scanning resumes after the count byte.
pub fn rle4(nt: &[u8]) -> Vec<u8> {
    let n = nt.len();
    let mut out = Vec::with_capacity(n + n / 4);
    let mut i = 0usize;
    let mut lit = 0usize; // start of the pending literal stretch
    while i + 4 < n {
        let c = nt[i];
        if nt[i + 1] == c && nt[i + 2] == c && nt[i + 3] == c {
            out.extend_from_slice(&nt[lit..i]);
            let k = nt[i + 4] as usize + 4;
            out.resize(out.len() + k, c);
            i += 5;
            lit = i;
        } else {
            i += 1;
        }
    }
    out.extend_from_slice(&nt[lit..]);
    out
}
