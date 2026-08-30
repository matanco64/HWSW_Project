//! Native symbol-decode kernel for the pyperformance `pyflate` benchmark.
//!
//! # Scope: one stage of the bzip2 pipeline, and deliberately not one more
//!
//! `bm_pyflate` decodes bzip2, not DEFLATE (the shipped `interpreter.tar.bz2`
//! starts with magic `0x425a`).  Its per-block pipeline is
//!
//! ```text
//!   header -> selectors -> code lengths -> [ SYMBOL DECODE ] -> inverse BWT -> RLE4 -> md5
//!                                          ^^^^^^^^^^^^^^^^^
//!                                          this crate, and only this
//! ```
//!
//! **In scope** — the loop this crate replaces, exactly:
//!
//!   1. MSB-first bit reader over the compressed buffer,
//!   2. canonical Huffman decode (flat primary table + `limit`/`base`/`perm`
//!      fallback), with the **table swap every 50 symbols** driven by the
//!      selector list,
//!   3. move-to-front over the `symbols_in_use - 2` entry favourites list,
//!   4. RUNA/RUNB run-length expansion.
//!
//! Output: the rank-mapped byte stream `L` (the *input* to the inverse BWT)
//! plus the final absolute bit position in the compressed buffer.
//!
//! **Out of scope, on purpose:**
//!
//! * `bwt_reverse` / the inverse-BWT chain walk.  It is an irreducibly serial
//!   399 KB data-dependent pointer chase; `dev/pyflate/FINDINGS.md` §1d shows
//!   five formulations that all land within ~20% of each other, and the whole
//!   point of the report's argument is that *neither* Python nor Rust nor a
//!   decode engine fixes it — that is what motivates the PIM discussion.
//!   Porting it here would replace a clean argument with a muddy one.
//! * The final RLE4 expansion (already O(runs) in Python via one regex).
//! * `bzip2_main` as a whole.  A native `bzip2_main` is benchmark deletion:
//!   `bm_pyflate` exists to time a *pure-Python decompressor*, and if the whole
//!   decompressor is native the remaining Python is an `open()` and a hash.
//!   The line drawn here is the line CPython itself draws with `_json` and
//!   `_pickle`: a native kernel may replace an inner loop the profile
//!   identifies; it may not replace the program.
//!
//! Header parsing, `compute_used`, `compute_selectors_list`, the delta-coded
//! code-length bit loop, table *reading*, block orchestration, the inverse BWT,
//! RLE4 and the MD5 check all stay in Python.
//!
//! # Why this exact boundary: one interface, three consumers
//!
//! This is the same cut as the proposed hardware in `hw/`: `huffman_engine`
//! (bit aligner + canonical decode + the 50-symbol selector FSM) followed by
//! `mtf_cam` (the 256-entry shift-register CAM) and the RUNA/RUNB expander.
//! So the FFI signature below is simultaneously
//!
//! * the **native software tier**'s entry point,
//! * the accelerator's **register map / DMA descriptor** — `BlockDecoder::new`
//!   is the config-region write (compressed buffer base, per-group code-length
//!   tables, selector list, initial MTF contents), `decode(bit_pos)` is the
//!   doorbell write with a start-offset register, and the returned
//!   `(bytes, end_bit_pos)` is the read-back window (output buffer + final
//!   stream position); this is the shape Intel's IAA uses for DEFLATE, where
//!   the Huffman tables live in an AECS config region,
//! * the **RTL golden model**'s reference vector source — see [`BlockDecoder::trace`].
//!
//! Drawing the software boundary anywhere else would mean maintaining a
//! separate hardware interface, and the report would lose the claim that the
//! three views are one design.
//!
//! # Correctness contract: byte-exactness, proven not asserted
//!
//! `rust/nbody` has a floating-point contract.  This crate has an integer one,
//! which is stricter and easier at the same time: **the symbol stream returned
//! by [`BlockDecoder::decode`] must be `==` to the `bytearray` the Python T3
//! implementation (`benchmarks/bm_pyflate/run_benchmark.py`,
//! `dev/pyflate/t3_table.py`) accumulates for the same block, and the returned
//! end bit position must equal Python's reader position after its symbol
//! loop.**  Feeding that stream onward through the *unmodified* Python inverse
//! BWT and RLE4 must reproduce the benchmark's 399,360 output bytes and its
//! `afa004a630fe072901b1d9628b960974` MD5.
//!
//! That is not asserted here; it is proven by `dev/pyflate/rs_check.py`, which
//! compares against both the Python T3 symbol loop *and* CPython's own `bz2`
//! module.  Every arithmetic step below is written to mirror the Python
//! expression it replaces, in the same order, so that a divergence is a bug
//! rather than a tolerance.
//!
//! Two places where the mirror is deliberately *not* literal, both documented
//! at the call site: the selector-exhaustion guard (`<` here, `<=` in the
//! Python, which would raise `IndexError` rather than do anything useful), and
//! the input tail padding (owned by this crate rather than by the caller).

use std::fs::File;
use std::io::{BufWriter, Write};

use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;

/// Width of the flat primary lookup table, in bits.
///
/// Measured on this stream (`dev/pyflate/FINDINGS.md` §1b): 11 bits resolves
/// **99.6%** of symbols in a single index, and the table is `1 << 11` `u32`s =
/// 8 KB per group, L1-resident for all six groups at once.  End-to-end time in
/// Python was flat for any value in 9..13; in Rust the table is cheaper still
/// because there is no interpreter overhead for the fallback path to hide
/// behind.  Codes longer than this fall back to canonical bit-at-a-time
/// extension over `limit`/`base`/`perm`, which *is* the classic two-level
/// table with the secondary tables replaced by arrays we already have.
const PRIMARY_BITS: u32 = 11;

/// bzip2 caps code lengths at 20 bits (`BZ_MAX_CODE_LEN` is 23; the encoder
/// never emits more than 20).  The refill keeps >= 32 bits buffered, so a
/// whole code is always resident and the decode loop never has to re-check.
const MAX_CODE_LEN: u32 = 23;

/// Tail padding appended to the caller's buffer so that a 32-bit refill on the
/// last symbol of the stream cannot run off the end.  The Python tier pushes
/// this requirement onto its caller; here the crate owns it, because a native
/// kernel that reads out of bounds when handed a short buffer is a much worse
/// bug than one extra 67 KB copy per block (~10 us against a ~150 ms block).
const TAIL_PAD: usize = 8;

/// One Huffman group's decode tables, in the libbzip2 `hbCreateDecodeTables`
/// shape plus a flat primary table on top.
///
/// This struct is the accelerator's per-group config region: `tbl` is the
/// primary decode RAM, `limit`/`base` are the per-length comparator/offset
/// register files, and `perm` is the symbol RAM.
struct Group {
    /// Effective primary width, `min(PRIMARY_BITS, max_len)`.
    pb: u32,
    /// `(1 << pb) - 1`.
    pmask: u64,
    /// `tbl[peek(pb)] == (symbol << 5) | code_length`, or 0 meaning "longer
    /// than `pb` bits, use `limit`/`base`/`perm`".  0 is unambiguous because a
    /// real entry always carries a non-zero length in its low 5 bits.
    tbl: Vec<u32>,
    /// `limit[l]` = largest assigned `l`-bit canonical code.  Indexed by code
    /// length; `i64` because the Python is arbitrary-precision and `vec - 1`
    /// is -1 for an empty leading length.
    limit: Vec<i64>,
    /// `base[l]` = offset such that `perm[code - base[l]]` is the symbol.
    base: Vec<i64>,
    /// Symbols in canonical order, i.e. sorted by `(length, symbol)`.
    perm: Vec<u16>,
    min_len: u32,
    max_len: u32,
}

impl Group {
    /// Mirrors `build_canonical()` + `build_table()` of `dev/pyflate/t3_table.py`
    /// (and `build_huffman_table()` in the landed benchmark), operation for
    /// operation.
    fn build(lengths: &[u8]) -> Result<Group, String> {
        let n = lengths.len();
        if n == 0 {
            return Err("empty code-length vector".into());
        }
        let min_len = lengths.iter().copied().filter(|&l| l != 0).min().ok_or(
            "code-length vector is all zeros: the group encodes no symbols",
        )? as u32;
        let max_len = lengths.iter().copied().max().unwrap() as u32;
        if max_len > MAX_CODE_LEN {
            return Err(format!("code length {max_len} exceeds bzip2's maximum"));
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

        Ok(Group { pb, pmask: (1u64 << pb) - 1, tbl, limit, base, perm, min_len, max_len })
    }
}

/// MSB-first bit reader over the padded compressed buffer.
///
/// The `u64` accumulator holds the next `nbits` unconsumed bits left-aligned
/// against bit `nbits - 1`; bits above `nbits` are always zero.  `refill()`
/// tops it up 32 bits at a time, which is the same 4-byte refill the Python
/// tier does with `int.from_bytes(data[pos:pos+4], 'big')` -- deliberately, so
/// that the two readers consume the stream in the same order and a mismatch
/// localises immediately.
///
/// In hardware this is the 64-bit barrel-shifter bit aligner in front of the
/// comparator cascade; `refill` is its prefetch.
struct BitReader<'a> {
    data: &'a [u8],
    /// Byte offset of the next byte to pull into `acc`.
    pos: usize,
    acc: u64,
    nbits: u32,
}

impl<'a> BitReader<'a> {
    /// Position the reader at absolute bit offset `bit_pos` of `data`.
    fn new(data: &'a [u8], bit_pos: u64) -> Result<BitReader<'a>, String> {
        let mut r = BitReader { data, pos: (bit_pos >> 3) as usize, acc: 0, nbits: 0 };
        r.refill()?;
        // Discard the sub-byte part of the start offset.
        let skip = (bit_pos & 7) as u32;
        r.nbits -= skip;
        r.acc &= mask(r.nbits);
        Ok(r)
    }

    /// Ensure at least 32 bits are buffered.  One 4-byte big-endian load; the
    /// precondition `nbits < 32` makes a single load sufficient.
    #[inline(always)]
    fn refill(&mut self) -> Result<(), String> {
        if self.nbits < 32 {
            if self.pos + 4 > self.data.len() {
                return Err("bit reader ran off the end of the compressed buffer".into());
            }
            let word = u32::from_be_bytes([
                self.data[self.pos],
                self.data[self.pos + 1],
                self.data[self.pos + 2],
                self.data[self.pos + 3],
            ]);
            self.acc = (self.acc << 32) | word as u64;
            self.nbits += 32;
            self.pos += 4;
        }
        Ok(())
    }

    /// Absolute bit offset of the next unconsumed bit.
    #[inline]
    fn bit_pos(&self) -> u64 {
        (self.pos as u64) * 8 - self.nbits as u64
    }
}

#[inline(always)]
fn mask(n: u32) -> u64 {
    if n >= 64 {
        u64::MAX
    } else {
        (1u64 << n) - 1
    }
}

/// Golden-trace sink.  See [`BlockDecoder::trace`] for the on-disk format.
#[derive(Default)]
struct Trace {
    sym: Vec<u16>,
    len: Vec<u8>,
    grp: Vec<u8>,
}

/// One bzip2 block's symbol-decode engine, configured once and re-runnable.
///
/// Construction is the config-region write: the compressed buffer, the six
/// per-group code-length vectors, the selector list and the initial
/// move-to-front contents all land Rust-side.  [`decode`](Self::decode) then
/// takes only a start bit offset, which keeps the doorbell cheap and -- more
/// usefully for benchmarking -- makes the call **idempotent**, so a min-of-N
/// timing loop measures the same work every round.
#[pyclass]
pub struct BlockDecoder {
    /// The caller's compressed buffer plus `TAIL_PAD` zero bytes.
    data: Vec<u8>,
    groups: Vec<Group>,
    /// Group index to use for each run of 50 symbols.
    selectors: Vec<u8>,
    /// Initial move-to-front list, front first: `[i for i, x in enumerate(used) if x]`.
    mtf_init: Vec<u8>,
    /// `symbols_in_use - 1`; the end-of-block symbol.
    eob: u32,
    symbols_in_use: u32,
}

#[pymethods]
impl BlockDecoder {
    /// Configure a decoder for one block.
    ///
    /// * `data` — the whole compressed stream (not just the block).  Copied,
    ///   with tail padding added; the caller keeps ownership of its `bytes`.
    /// * `code_lengths` — one vector of `symbols_in_use` code lengths per
    ///   Huffman group, exactly what the Python delta-coded bit loop produces.
    /// * `selectors` — the MTF-decoded selector list, one group index per run
    ///   of 50 symbols.
    /// * `symbols_in_use` — `sum(used) + 2` (the two RUNA/RUNB symbols).
    /// * `favourites` — the initial MTF list, **front first** (i.e. the
    ///   un-reversed `[i for i, x in enumerate(used) if x]`; the Python tier
    ///   stores it reversed as a `list.pop` micro-optimisation, which is a
    ///   Python-list detail with no analogue in an array).
    #[new]
    fn new(
        data: &[u8],
        code_lengths: Vec<Vec<u8>>,
        selectors: Vec<u8>,
        symbols_in_use: u32,
        favourites: Vec<u8>,
    ) -> PyResult<Self> {
        if !(3..=258).contains(&symbols_in_use) {
            return Err(PyValueError::new_err("symbols_in_use out of range 3..258"));
        }
        if favourites.len() + 2 != symbols_in_use as usize {
            return Err(PyValueError::new_err(format!(
                "favourites has {} entries, expected symbols_in_use - 2 = {}",
                favourites.len(),
                symbols_in_use - 2
            )));
        }
        if !(2..=6).contains(&code_lengths.len()) {
            return Err(PyValueError::new_err("number of Huffman groups not in 2..6"));
        }
        let mut groups = Vec::with_capacity(code_lengths.len());
        for (g, lengths) in code_lengths.iter().enumerate() {
            if lengths.len() != symbols_in_use as usize {
                return Err(PyValueError::new_err(format!(
                    "group {g} has {} code lengths, expected {symbols_in_use}",
                    lengths.len()
                )));
            }
            groups.push(Group::build(lengths).map_err(PyValueError::new_err)?);
        }
        if let Some(&bad) = selectors.iter().find(|&&s| s as usize >= groups.len()) {
            return Err(PyValueError::new_err(format!(
                "selector {bad} names a group that does not exist"
            )));
        }

        let mut padded = Vec::with_capacity(data.len() + TAIL_PAD);
        padded.extend_from_slice(data);
        padded.resize(data.len() + TAIL_PAD, 0);

        Ok(BlockDecoder {
            data: padded,
            groups,
            selectors,
            mtf_init: favourites,
            eob: symbols_in_use - 1,
            symbols_in_use,
        })
    }

    /// Decode the block starting at absolute bit offset `bit_pos`.
    ///
    /// Returns `(L, end_bit_pos)`: the rank-mapped byte stream that the
    /// inverse BWT consumes, and the absolute bit offset just past the
    /// end-of-block symbol.  The caller restores its Python bit reader with
    ///
    /// ```python
    /// field.pos, field.bits, field.bitfield = end_bit_pos >> 3, 0, 0
    /// field.readbits(end_bit_pos & 7)      # discard the sub-byte remainder
    /// ```
    fn decode<'py>(&self, py: Python<'py>, bit_pos: u64) -> PyResult<(Bound<'py, PyBytes>, u64)> {
        let (out, end) = py
            .allow_threads(|| self.run::<false>(bit_pos, &mut Trace::default()))
            .map_err(PyValueError::new_err)?;
        Ok((PyBytes::new_bound(py, &out), end))
    }

    /// Decode, and additionally write a golden reference vector to `path` for
    /// the `huffman_engine` / `mtf_cam` RTL testbenches.
    ///
    /// Returns `(n_symbols, n_out, end_bit_pos)`.
    ///
    /// # File format (little-endian throughout, 40-byte header)
    ///
    /// ```text
    ///   off  size        field
    ///     0     8        magic  b"PFTRACE1"
    ///     8     4  u32   version = 1
    ///    12     4  u32   n_sym   Huffman symbols decoded, INCLUDING the final EOB
    ///    16     4  u32   n_out   length of L in bytes
    ///    20     4  u32   symbols_in_use (alphabet size; EOB == this - 1)
    ///    24     8  u64   bit_pos_start
    ///    32     8  u64   bit_pos_end
    ///    40   2*n_sym u16 sym[i]  raw Huffman symbol value, decode order
    ///   ...     n_sym u8  len[i]  code length in bits consumed for sym[i]
    ///   ...     n_sym u8  grp[i]  group index in effect (== selectors[i / 50])
    ///   ...     n_out u8  L[j]    MTF + RUNA/RUNB decoded output byte
    /// ```
    ///
    /// `sym`/`len`/`grp` are the `huffman_engine` reference stream (one record
    /// per cycle of a 1-symbol/cycle engine, including the table swap the
    /// selector FSM must perform every 50 symbols).  `L` is the `mtf_cam` plus
    /// run-expander reference stream.  `grp` is derivable from the index but is
    /// written explicitly so a testbench need not reimplement the /50 rule to
    /// check it.
    ///
    /// For this benchmark's single block the file is ~929 KB
    /// (148,271 symbols x 4 bytes + 336,184 output bytes + 40).
    fn trace(&self, py: Python<'_>, bit_pos: u64, path: &str) -> PyResult<(usize, usize, u64)> {
        let mut tr = Trace::default();
        let (out, end) = py
            .allow_threads(|| self.run::<true>(bit_pos, &mut tr))
            .map_err(PyValueError::new_err)?;

        let f = File::create(path).map_err(|e| PyIOError::new_err(e.to_string()))?;
        let mut w = BufWriter::new(f);
        let write = |w: &mut BufWriter<File>, tr: &Trace, out: &[u8]| -> std::io::Result<()> {
            w.write_all(b"PFTRACE1")?;
            w.write_all(&1u32.to_le_bytes())?;
            w.write_all(&(tr.sym.len() as u32).to_le_bytes())?;
            w.write_all(&(out.len() as u32).to_le_bytes())?;
            w.write_all(&self.symbols_in_use.to_le_bytes())?;
            w.write_all(&bit_pos.to_le_bytes())?;
            w.write_all(&end.to_le_bytes())?;
            for &s in &tr.sym {
                w.write_all(&s.to_le_bytes())?;
            }
            w.write_all(&tr.len)?;
            w.write_all(&tr.grp)?;
            w.write_all(out)?;
            w.flush()
        };
        write(&mut w, &tr, &out).map_err(|e| PyIOError::new_err(e.to_string()))?;
        Ok((tr.sym.len(), out.len(), end))
    }

    /// Per-group decode tables, for generating the accelerator's config region
    /// and for cross-checking the RTL's table build against this one.
    ///
    /// Returns one `(min_len, max_len, primary_bits, limit, base, perm)` per
    /// group, in group order.
    fn group_tables(&self) -> Vec<(u32, u32, u32, Vec<i64>, Vec<i64>, Vec<u16>)> {
        self.groups
            .iter()
            .map(|g| {
                (g.min_len, g.max_len, g.pb, g.limit.clone(), g.base.clone(), g.perm.clone())
            })
            .collect()
    }

    #[getter]
    fn num_groups(&self) -> usize {
        self.groups.len()
    }

    #[getter]
    fn primary_bits(&self) -> u32 {
        PRIMARY_BITS
    }

    fn __repr__(&self) -> String {
        format!(
            "BlockDecoder(groups={}, selectors={}, alphabet={}, primary_bits={})",
            self.groups.len(),
            self.selectors.len(),
            self.symbols_in_use,
            PRIMARY_BITS
        )
    }
}

impl BlockDecoder {
    /// The kernel: bit reader -> canonical Huffman -> MTF -> RUNA/RUNB.
    ///
    /// `TRACE` is a const generic rather than an `Option` argument so the
    /// tracing branch is monomorphised away entirely in the hot
    /// `run::<false>` instantiation -- the golden-trace mode costs the
    /// production path nothing.
    ///
    /// Every step mirrors the Python T3 symbol loop; see the correctness
    /// contract in the module docs.
    fn run<const TRACE: bool>(
        &self,
        bit_pos: u64,
        tr: &mut Trace,
    ) -> Result<(Vec<u8>, u64), String> {
        let mut br = BitReader::new(&self.data, bit_pos)?;

        // MTF list, front first.  A plain array with `copy_within` for the
        // shift: at the measured mean rank of 7.2 (FINDINGS §1e) that is a
        // ~7-byte memmove.  This array IS the shift-register CAM of the
        // hardware proposal, which is why the two designs mirror each other.
        let mut mtf = self.mtf_init.clone();
        let nmtf = mtf.len();

        // One allocation, never grown: 1 MiB is above bzip2's largest possible
        // block (blocksize 9 = 900,000 bytes of L), and this block is 336,184.
        let mut out: Vec<u8> = Vec::with_capacity(1 << 20);

        let eob = self.eob;
        let nsel = self.selectors.len();
        let mut sel_ptr = 0usize;
        // Symbols left before the next table swap.  Starts at 0 so the first
        // iteration loads a group, exactly as the Python `decoded` counter does.
        let mut decoded: i32 = 0;
        let mut group = &self.groups[0];
        let mut cur_group: u8 = 0;

        let mut repeat: u64 = 0;
        let mut repeat_power: u64 = 0;

        loop {
            decoded -= 1;
            if decoded <= 0 {
                decoded = 50; // bzip2's fixed table re-evaluation interval
                // NOT a literal mirror: the Python writes `if selector_pointer
                // <= nsel`, which for an exhausted selector list would raise
                // IndexError rather than do anything useful.  `<` is the same
                // behaviour on every well-formed stream and merely keeps the
                // last group in effect instead of panicking on a malformed one.
                if sel_ptr < nsel {
                    cur_group = self.selectors[sel_ptr];
                    group = &self.groups[cur_group as usize];
                    sel_ptr += 1;
                }
            }

            // Keep >= 32 bits buffered; the longest bzip2 code is 20 bits, so
            // a whole code is always resident and the decode below never
            // re-checks the buffer.
            br.refill()?;

            // ---- canonical Huffman decode -------------------------------
            // One array index resolves 99.6% of symbols; the rest extend the
            // code one bit at a time against limit[]/base[]/perm[].
            let zvec = (br.acc >> (br.nbits - group.pb)) & group.pmask;
            let v = group.tbl[zvec as usize];
            let r: u32;
            let used_bits: u32;
            if v != 0 {
                used_bits = v & 31;
                br.nbits -= used_bits;
                r = v >> 5;
            } else {
                let mut zn = group.pb;
                let mut z = zvec as i64;
                while z > group.limit[zn as usize] {
                    zn += 1;
                    if zn > group.max_len {
                        return Err("no Huffman code matches the next bits".into());
                    }
                    z = (z << 1) | ((br.acc >> (br.nbits - zn)) & 1) as i64;
                }
                br.nbits -= zn;
                let idx = z - group.base[zn as usize];
                if idx < 0 || idx as usize >= group.perm.len() {
                    return Err("Huffman symbol index out of range".into());
                }
                r = group.perm[idx as usize] as u32;
                used_bits = zn;
            }

            if TRACE {
                tr.sym.push(r as u16);
                tr.len.push(used_bits as u8);
                tr.grp.push(cur_group);
            }

            // ---- RUNA / RUNB bijective base-2 run length -----------------
            if r <= 1 {
                if repeat == 0 {
                    repeat_power = 1;
                }
                repeat += repeat_power << r;
                repeat_power <<= 1;
                if repeat_power == 0 || repeat > (1 << 40) {
                    return Err("RUNA/RUNB run length overflowed".into());
                }
                continue;
            } else if repeat > 0 {
                // Remember kids: if there is only one repeated real symbol it
                // is encoded with *zero* Huffman bits and never output, so the
                // repeated byte is the head of the MTF list, not out[-1].
                let head = mtf[0];
                let n = out.len();
                out.resize(n + repeat as usize, head);
                repeat = 0;
            }

            if r == eob {
                break;
            }

            // ---- move to front ------------------------------------------
            // Symbol r >= 2 addresses MTF rank r - 1.
            let rank = (r - 1) as usize;
            if rank >= nmtf {
                return Err("MTF rank beyond the favourites list".into());
            }
            let o = mtf[rank];
            mtf.copy_within(0..rank, 1);
            mtf[0] = o;
            out.push(o);
        }

        Ok((out, br.bit_pos()))
    }
}

/// One-shot convenience wrapper: configure, decode, discard.
///
/// Equivalent to `BlockDecoder(...).decode(bit_pos)`.  Present because the
/// hardware analogy is a single DMA descriptor submission, and because a
/// caller decoding a multi-block stream has no reason to keep the config
/// around.  Table construction is ~0.3% of block time (FINDINGS §1b), so the
/// difference is not a performance question.
#[pyfunction]
fn decode_block<'py>(
    py: Python<'py>,
    data: &[u8],
    bit_pos: u64,
    code_lengths: Vec<Vec<u8>>,
    selectors: Vec<u8>,
    symbols_in_use: u32,
    favourites: Vec<u8>,
) -> PyResult<(Bound<'py, PyBytes>, u64)> {
    let dec = BlockDecoder::new(data, code_lengths, selectors, symbols_in_use, favourites)?;
    dec.decode(py, bit_pos)
}

#[pymodule]
fn pyflate_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BlockDecoder>()?;
    m.add_function(wrap_pyfunction!(decode_block, m)?)?;
    m.add("PRIMARY_BITS", PRIMARY_BITS)?;
    Ok(())
}
