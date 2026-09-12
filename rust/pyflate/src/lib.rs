//! Native Huffman/MTF/RUNA-RUNB stage for the pyflate bzip2 benchmark.
//!
//! Input is a compressed stream, code lengths, selectors, initial MTF contents,
//! and a start bit offset. Output is the BWT input byte stream and exact end
//! bit offset. Header parsing, inverse BWT, RLE4, and validation stay in Python.
//!
//! The Python API remains `BlockDecoder`, `decode_block`, and `PRIMARY_BITS`.
//! The numerical kernel is independent of PyO3 so its bit accounting, selector
//! changes, MTF/run expansion, and golden traces can be unit-tested directly.
//! Full-stream cross-checks live in `dev/pyflate/rs_check.py`.

mod bindings;
mod bit_reader;
mod decoder;
mod huffman;
mod trace;
