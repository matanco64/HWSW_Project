//! Python-independent block configuration and Huffman/MTF/RUNA-RUNB loop.
//! Valid streams retain the existing selector schedule and bit consumption.

use crate::bit_reader::BitReader;
use crate::huffman::Group;
use crate::trace::Trace;

const TAIL_PAD: usize = 8;

pub(crate) struct Decoder {
    /// The caller's compressed buffer plus `TAIL_PAD` zero bytes.
    data: Vec<u8>,
    pub(crate) groups: Vec<Group>,
    /// Group index to use for each run of 50 symbols.
    pub(crate) selectors: Vec<u8>,
    /// Initial move-to-front list, front first: `[i for i, x in enumerate(used) if x]`.
    mtf_init: Vec<u8>,
    /// `symbols_in_use - 1`; the end-of-block symbol.
    eob: u32,
    pub(crate) symbols_in_use: u32,
}

impl Decoder {
    pub(crate) fn new(
        data: &[u8],
        code_lengths: Vec<Vec<u8>>,
        selectors: Vec<u8>,
        symbols_in_use: u32,
        favourites: Vec<u8>,
    ) -> Result<Self, String> {
        if !(3..=258).contains(&symbols_in_use) {
            return Err("symbols_in_use out of range 3..258".into());
        }
        if favourites.len() + 2 != symbols_in_use as usize {
            return Err(format!(
                "favourites has {} entries, expected symbols_in_use - 2 = {}",
                favourites.len(),
                symbols_in_use - 2
            ));
        }
        if !(2..=6).contains(&code_lengths.len()) {
            return Err("number of Huffman groups not in 2..6".into());
        }
        let mut groups = Vec::with_capacity(code_lengths.len());
        for (g, lengths) in code_lengths.iter().enumerate() {
            if lengths.len() != symbols_in_use as usize {
                return Err(format!(
                    "group {g} has {} code lengths, expected {symbols_in_use}",
                    lengths.len()
                ));
            }
            groups.push(Group::build(lengths)?);
        }
        if let Some(&bad) = selectors.iter().find(|&&s| s as usize >= groups.len()) {
            return Err(format!("selector {bad} names a group that does not exist"));
        }

        let mut padded = Vec::with_capacity(data.len() + TAIL_PAD);
        padded.extend_from_slice(data);
        padded.resize(data.len() + TAIL_PAD, 0);

        Ok(Decoder {
            data: padded,
            groups,
            selectors,
            mtf_init: favourites,
            eob: symbols_in_use - 1,
            symbols_in_use,
        })
    }
}
impl Decoder {
    /// The kernel: bit reader -> canonical Huffman -> MTF -> RUNA/RUNB.
    ///
    /// `TRACE` is a const generic rather than an `Option` argument so the
    /// tracing branch is monomorphised away entirely in the hot
    /// `run::<false>` instantiation -- the golden-trace mode costs the
    /// production path nothing.
    ///
    /// Every step mirrors the Python T3 symbol loop; see the correctness
    /// contract in the module docs.
    pub(crate) fn run<const TRACE: bool>(
        &self,
        bit_pos: u64,
        tr: &mut Trace,
    ) -> Result<(Vec<u8>, u64), String> {
        let mut br = BitReader::new(&self.data, bit_pos)?;

        // MTF list, front first.  A plain array with `copy_within` for the
        // shift touches rank bytes. The hardware proposal likewise selects by
        // rank and shifts the preceding entries; it is not a content search.
        let mut mtf = self.mtf_init.clone();
        let nmtf = mtf.len();

        // One allocation for a valid block: 1 MiB is above bzip2's largest
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

            let (r, used_bits) = group.decode(&mut br)?;

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
