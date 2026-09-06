//! Canonical Huffman tables: an 11-bit primary lookup and long-code fallback.

use crate::bit_reader::BitReader;

/// Per-group table width; each full table occupies 8 KiB.
pub(crate) const PRIMARY_BITS: u32 = 11;
/// Legacy accepted limit retained for API compatibility; the benchmark's
/// bzip2 header parser restricts format code lengths to 20 bits.
const MAX_CODE_LEN: u32 = 23;

pub(crate) struct Group {
    /// Effective primary width, `min(PRIMARY_BITS, max_len)`.
    pub(crate) pb: u32,
    /// `(1 << pb) - 1`.
    pmask: u64,
    /// `tbl[peek(pb)] == (symbol << 5) | code_length`, or 0 meaning "longer
    /// than `pb` bits, use `limit`/`base`/`perm`".  0 is unambiguous because a
    /// real entry always carries a non-zero length in its low 5 bits.
    tbl: Vec<u32>,
    /// `limit[l]` = largest assigned `l`-bit canonical code.  Indexed by code
    /// length; `i64` because the Python is arbitrary-precision and `vec - 1`
    /// is -1 for an empty leading length.
    pub(crate) limit: Vec<i64>,
    /// `base[l]` = offset such that `perm[code - base[l]]` is the symbol.
    pub(crate) base: Vec<i64>,
    /// Symbols in canonical order, i.e. sorted by `(length, symbol)`.
    pub(crate) perm: Vec<u16>,
    pub(crate) min_len: u32,
    pub(crate) max_len: u32,
}

impl Group {
    /// Mirrors `build_canonical()` + `build_table()` of `dev/pyflate/t3_table.py`
    /// (and `build_huffman_table()` in the landed benchmark), operation for
    /// operation.
    pub(crate) fn build(lengths: &[u8]) -> Result<Group, String> {
        let n = lengths.len();
        if n == 0 {
            return Err("empty code-length vector".into());
        }
        let min_len = lengths
            .iter()
            .copied()
            .filter(|&l| l != 0)
            .min()
            .ok_or("code-length vector is all zeros: the group encodes no symbols")?
            as u32;
        let max_len = lengths.iter().copied().max().unwrap() as u32;
        if max_len > MAX_CODE_LEN {
            return Err(format!(
                "code length {max_len} exceeds the decoder's legacy limit {MAX_CODE_LEN}"
            ));
        }

        // perm[]: symbols in canonical (length, symbol) order.
        let mut perm: Vec<u16> = Vec::with_capacity(n);
        for l in min_len..=max_len {
            for (s, &ls) in lengths.iter().enumerate() {
                if ls as u32 == l {
                    perm.push(s as u16);
                }
            }
        }

        let mut count = vec![0i64; max_len as usize + 2];
        for &l in lengths {
            if l != 0 {
                count[l as usize] += 1;
            }
        }

        // Canonical code assignment: codes handed out in increasing
        // (length, symbol) order starting at zero, shifted left by one at each
        // length increment -- identical to the stock `populate_huffman_symbols`.
        let mut limit = vec![0i64; max_len as usize + 2];
        let mut base = vec![0i64; max_len as usize + 2];
        let mut vec_ = 0i64;
        let mut cum = 0i64;
        for l in min_len..=max_len {
            vec_ += count[l as usize];
            if vec_ > (1i64 << l) {
                return Err("oversubscribed Huffman code lengths".into());
            }
            limit[l as usize] = vec_ - 1;
            base[l as usize] = (vec_ - count[l as usize]) - cum;
            cum += count[l as usize];
            vec_ <<= 1;
        }

        // Flat primary table.  Because bzip2 codes are canonical AND MSB-first,
        // the slots belonging to consecutive symbols in canonical order are
        // CONTIGUOUS, so this is ~147 span fills rather than 2^pb per-slot
        // writes.  (Same trick as the Python tier's `tbl += [v] * span`.)
        let pb = PRIMARY_BITS.min(max_len);
        let mut tbl = vec![0u32; 1usize << pb];
        let mut at = 0usize;
        for &s in &perm {
            let l = lengths[s as usize] as u32;
            if l > pb {
                break;
            }
            let span = 1usize << (pb - l);
            let entry = ((s as u32) << 5) | l;
            tbl[at..at + span].fill(entry);
            at += span;
        }

        Ok(Group {
            pb,
            pmask: (1u64 << pb) - 1,
            tbl,
            limit,
            base,
            perm,
            min_len,
            max_len,
        })
    }
}

impl Group {
    /// Consume one code, returning its symbol and exact code length.
    #[inline(always)]
    pub(crate) fn decode(&self, br: &mut BitReader<'_>) -> Result<(u32, u32), String> {
        // One array index resolves 99.6% of symbols; the rest extend the
        // code one bit at a time against limit[]/base[]/perm[].
        let zvec = (br.acc >> (br.nbits - self.pb)) & self.pmask;
        let v = self.tbl[zvec as usize];
        let r: u32;
        let used_bits: u32;
        if v != 0 {
            used_bits = v & 31;
            br.nbits -= used_bits;
            r = v >> 5;
        } else {
            let mut zn = self.pb;
            let mut z = zvec as i64;
            while z > self.limit[zn as usize] {
                zn += 1;
                if zn > self.max_len {
                    return Err("no Huffman code matches the next bits".into());
                }
                z = (z << 1) | ((br.acc >> (br.nbits - zn)) & 1) as i64;
            }
            br.nbits -= zn;
            let idx = z - self.base[zn as usize];
            if idx < 0 || idx as usize >= self.perm.len() {
                return Err("Huffman symbol index out of range".into());
            }
            r = self.perm[idx as usize] as u32;
            used_bits = zn;
        }

        Ok((r, used_bits))
    }
}
