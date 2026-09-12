//! Stable Python API; computation and trace formatting live in Rust-only modules.

use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::fs::File;
use std::io::BufWriter;

use crate::decoder::Decoder;
use crate::huffman::PRIMARY_BITS;
use crate::trace::Trace;

/// Reusable configuration for one bzip2 block's symbol-decode stage.
#[pyclass]
pub struct BlockDecoder {
    inner: Decoder,
}

#[pymethods]
impl BlockDecoder {
    /// Configure from the whole compressed stream, per-group code lengths,
    /// selectors (one group per 50 symbols), alphabet size, and front-first
    /// MTF favourites. Input is copied; each decode starts from fresh state.
    #[new]
    fn new(
        data: &[u8],
        code_lengths: Vec<Vec<u8>>,
        selectors: Vec<u8>,
        symbols_in_use: u32,
        favourites: Vec<u8>,
    ) -> PyResult<Self> {
        Decoder::new(data, code_lengths, selectors, symbols_in_use, favourites)
            .map(|inner| Self { inner })
            .map_err(PyValueError::new_err)
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
            .allow_threads(|| self.inner.run::<false>(bit_pos, &mut Trace::default()))
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
            .allow_threads(|| self.inner.run::<true>(bit_pos, &mut tr))
            .map_err(PyValueError::new_err)?;

        let f = File::create(path).map_err(|e| PyIOError::new_err(e.to_string()))?;
        let mut w = BufWriter::new(f);
        tr.write(&mut w, &out, self.inner.symbols_in_use, bit_pos, end)
            .map_err(|e| PyIOError::new_err(e.to_string()))?;
        Ok((tr.sym.len(), out.len(), end))
    }

    /// Per-group decode tables, for generating the accelerator's config region
    /// and for cross-checking the RTL's table build against this one.
    ///
    /// Returns one `(min_len, max_len, primary_bits, limit, base, perm)` per
    /// group, in group order.
    fn group_tables(&self) -> Vec<(u32, u32, u32, Vec<i64>, Vec<i64>, Vec<u16>)> {
        self.inner
            .groups
            .iter()
            .map(|g| {
                (
                    g.min_len,
                    g.max_len,
                    g.pb,
                    g.limit.clone(),
                    g.base.clone(),
                    g.perm.clone(),
                )
            })
            .collect()
    }

    #[getter]
    fn num_groups(&self) -> usize {
        self.inner.groups.len()
    }

    #[getter]
    fn primary_bits(&self) -> u32 {
        PRIMARY_BITS
    }

    fn __repr__(&self) -> String {
        format!(
            "BlockDecoder(groups={}, selectors={}, alphabet={}, primary_bits={})",
            self.inner.groups.len(),
            self.inner.selectors.len(),
            self.inner.symbols_in_use,
            PRIMARY_BITS
        )
    }
}

/// One-shot convenience wrapper: configure, decode, discard.
///
/// Equivalent to `BlockDecoder(...).decode(bit_pos)`, including configuration
/// and input-copy costs on every call.
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
