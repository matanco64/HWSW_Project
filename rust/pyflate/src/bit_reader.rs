//! MSB-first reader with 32-bit refills and absolute bit-position accounting.

pub(crate) struct BitReader<'a> {
    data: &'a [u8],
    /// Byte offset of the next byte to pull into `acc`.
    pos: usize,
    pub(crate) acc: u64,
    pub(crate) nbits: u32,
}

impl<'a> BitReader<'a> {
    /// Position the reader at absolute bit offset `bit_pos` of `data`.
    pub(crate) fn new(data: &'a [u8], bit_pos: u64) -> Result<BitReader<'a>, String> {
        if bit_pos / 8 > data.len() as u64 {
            return Err("start bit position is outside the compressed buffer".into());
        }
        let mut r = BitReader {
            data,
            pos: (bit_pos >> 3) as usize,
            acc: 0,
            nbits: 0,
        };
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
    pub(crate) fn refill(&mut self) -> Result<(), String> {
        if self.nbits < 32 {
            if self.data.len().saturating_sub(self.pos) < 4 {
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
    pub(crate) fn bit_pos(&self) -> u64 {
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
