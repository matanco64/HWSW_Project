//! PFTRACE1 golden-vector serialization, separate from decoding and Python I/O.

use std::io::{self, Write};

/// Raw Huffman symbols, consumed code lengths, and the active selector group.
#[derive(Default)]
pub(crate) struct Trace {
    pub(crate) sym: Vec<u16>,
    pub(crate) len: Vec<u8>,
    pub(crate) grp: Vec<u8>,
}

impl Trace {
    /// Write the existing little-endian format (40-byte header, then arrays).
    pub(crate) fn write(
        &self,
        mut w: impl Write,
        out: &[u8],
        symbols_in_use: u32,
        start: u64,
        end: u64,
    ) -> io::Result<()> {
        w.write_all(b"PFTRACE1")?;
        w.write_all(&1u32.to_le_bytes())?;
        w.write_all(&(self.sym.len() as u32).to_le_bytes())?;
        w.write_all(&(out.len() as u32).to_le_bytes())?;
        w.write_all(&symbols_in_use.to_le_bytes())?;
        w.write_all(&start.to_le_bytes())?;
        w.write_all(&end.to_le_bytes())?;
        for &symbol in &self.sym {
            w.write_all(&symbol.to_le_bytes())?;
        }
        w.write_all(&self.len)?;
        w.write_all(&self.grp)?;
        w.write_all(out)?;
        w.flush()
    }
}
