//! Rust-only tests: `cargo test --test kernel`, or `rustc --test tests/kernel.rs`.
//! No Python interpreter or extension-module linkage is needed by this harness.
#![allow(dead_code)]

#[path = "../src/bit_reader.rs"]
mod bit_reader;
#[path = "../src/decoder.rs"]
mod decoder;
#[path = "../src/huffman.rs"]
mod huffman;
#[path = "../src/trace.rs"]
mod trace;

use bit_reader::BitReader;
use decoder::Decoder;
use huffman::Group;
use trace::Trace;

fn packed(bits: &str) -> Vec<u8> {
    let mut data = vec![0; bits.len().div_ceil(8) + 8];
    for (i, bit) in bits.bytes().enumerate() {
        assert!(bit == b'0' || bit == b'1');
        data[i / 8] |= (bit - b'0') << (7 - i % 8);
    }
    data
}

fn decoder(bits: &str, selectors: Vec<u8>) -> Decoder {
    // Four 2-bit codes: RUNA=00, RUNB=01, rank 1=10, EOB=11.
    Decoder::new(
        &packed(bits),
        vec![vec![2; 4]; 2],
        selectors,
        4,
        b"ab".to_vec(),
    )
    .unwrap()
}

#[test]
fn bit_reader_preserves_offsets_across_refills() {
    let data = packed("101101001100101010101111000011110101010101011100");
    for start in 0..8 {
        let mut reader = BitReader::new(&data, start).unwrap();
        assert_eq!(reader.bit_pos(), start);
        reader.nbits -= 23;
        reader.refill().unwrap();
        assert_eq!(reader.bit_pos(), start + 23);
        assert!(reader.nbits >= 32);
    }
    assert!(BitReader::new(&data, u64::MAX).is_err());
    assert!(BitReader::new(&[0; 3], 0).is_err());
}

#[test]
fn primary_lookup_consumes_only_the_code_length() {
    let group = Group::build(&[1, 2, 2]).unwrap();
    let data = packed("01011");
    let mut reader = BitReader::new(&data, 0).unwrap();
    for expected in [(0, 1), (1, 2), (2, 2)] {
        assert_eq!(group.decode(&mut reader).unwrap(), expected);
    }
    assert_eq!(reader.bit_pos(), 5);
}

#[test]
fn long_codes_use_canonical_fallback() {
    let mut lengths: Vec<u8> = (1..=12).collect();
    lengths.push(12);
    let group = Group::build(&lengths).unwrap();
    let data = packed("1111111111101111111111110");
    let mut reader = BitReader::new(&data, 0).unwrap();
    assert_eq!(group.decode(&mut reader).unwrap(), (11, 12));
    assert_eq!(group.decode(&mut reader).unwrap(), (12, 12));
    reader.refill().unwrap();
    assert_eq!(group.decode(&mut reader).unwrap(), (0, 1));
    assert_eq!(reader.bit_pos(), 25);
}

#[test]
fn invalid_tables_return_errors_instead_of_panicking() {
    for lengths in [vec![], vec![0, 0], vec![24], vec![1, 1, 1]] {
        assert!(Group::build(&lengths).is_err());
    }
    let group = Group::build(&[2, 2]).unwrap();
    let data = packed("11");
    assert!(group
        .decode(&mut BitReader::new(&data, 0).unwrap())
        .is_err());
}

#[test]
fn runs_flush_the_mtf_head_before_eob_and_decode_is_repeatable() {
    // rank 1 emits b; RUNA,RUNB encode five more b bytes; EOB flushes them.
    let decoder = decoder("10000111", vec![0]);
    for _ in 0..2 {
        let (out, end) = decoder.run::<false>(0, &mut Trace::default()).unwrap();
        assert_eq!(out, b"bbbbbb");
        assert_eq!(end, 8);
    }
}

#[test]
fn mtf_reorders_and_non_run_symbol_flushes_pending_run() {
    let decoder = decoder("10001011", vec![0]);
    let (out, end) = decoder.run::<false>(0, &mut Trace::default()).unwrap();
    assert_eq!(out, b"bba");
    assert_eq!(end, 8);
}

#[test]
fn non_byte_start_and_end_offsets_are_exact() {
    let decoder = decoder("1011011", vec![0]);
    let (out, end) = decoder.run::<false>(3, &mut Trace::default()).unwrap();
    assert_eq!(out, b"b");
    assert_eq!(end, 7);
}

#[test]
fn selectors_switch_after_exactly_fifty_symbols() {
    let decoder = Decoder::new(
        &packed(&("10".repeat(50) + "111")),
        vec![vec![2; 4], vec![1, 2, 3, 3]],
        vec![0, 1],
        4,
        b"ab".to_vec(),
    )
    .unwrap();
    let mut tr = Trace::default();
    let traced = decoder.run::<true>(0, &mut tr).unwrap();
    let plain = decoder.run::<false>(0, &mut Trace::default()).unwrap();
    assert_eq!(traced, plain);
    assert_eq!(traced.1, 103);
    assert_eq!(tr.grp[..50], [0; 50]);
    assert_eq!(tr.grp[50], 1);
    assert_eq!(tr.sym[50], 3);
    assert_eq!(tr.len[50], 3);
    assert_eq!(tr.len.iter().map(|&n| n as u64).sum::<u64>(), 103);
}

#[test]
fn golden_trace_preserves_binary_format() {
    let decoder = decoder("1011", vec![0]);
    let mut tr = Trace::default();
    let (out, end) = decoder.run::<true>(0, &mut tr).unwrap();
    let mut bytes = Vec::new();
    tr.write(&mut bytes, &out, 4, 0, end).unwrap();
    let mut expected = b"PFTRACE1".to_vec();
    for value in [1u32, 2, 1, 4] {
        expected.extend_from_slice(&value.to_le_bytes());
    }
    expected.extend_from_slice(&0u64.to_le_bytes());
    expected.extend_from_slice(&4u64.to_le_bytes());
    expected.extend_from_slice(&[2, 0, 3, 0, 2, 2, 0, 0, b'b']);
    assert_eq!(bytes, expected);
}

#[test]
fn configuration_validates_alphabet_groups_and_selectors() {
    assert!(Decoder::new(&[], vec![vec![2; 4]; 2], vec![2], 4, b"ab".to_vec()).is_err());
    assert!(Decoder::new(&[], vec![vec![2; 4]], vec![0], 4, b"ab".to_vec()).is_err());
    assert!(Decoder::new(&[], vec![vec![2; 3]; 2], vec![0], 4, b"ab".to_vec()).is_err());
    assert!(Decoder::new(&[], vec![vec![2; 4]; 2], vec![0], 4, b"a".to_vec()).is_err());
    assert!(Decoder::new(&[], vec![], vec![], 2, vec![]).is_err());
}

// ---------------------------------------------------------------------------
// Property test: random canonical codes, encoded independently, decoded back.
//
// The other tests here pin hand-written tables, and rs_check.py drives the one
// shipped stream, whose codes exercise the long-code fallback for 0.4% of its
// symbols. Neither says much about a table shape the benchmark happens not to
// contain. This builds random Kraft-complete length sets, assigns canonical
// codes with an encoder written independently of the decoder, and requires the
// decoder to return both the symbol and the bit position it consumed.
// ---------------------------------------------------------------------------

/// Deterministic xorshift64; the harness deliberately has no dependencies.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }

    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }
}

/// Random Kraft-complete lengths: start from one leaf and split a random leaf
/// until there are `n` of them, so sum(2^-len) == 1 holds by construction.
/// `skew` always splits the deepest available leaf, which drives the tree down
/// to `max_len` and is what reaches codes longer than the primary table; the
/// balanced random shape rarely gets past 11 bits on its own.
fn random_lengths(rng: &mut Rng, n: usize, max_len: u8, skew: bool) -> Option<Vec<u8>> {
    let mut depths: Vec<u8> = vec![0];
    while depths.len() < n {
        let open: Vec<usize> = (0..depths.len()).filter(|&i| depths[i] < max_len).collect();
        if open.is_empty() {
            return None;
        }
        let i = if skew {
            *open.iter().max_by_key(|&&i| depths[i]).unwrap()
        } else {
            open[rng.below(open.len())]
        };
        let d = depths[i] + 1;
        depths[i] = d;
        depths.push(d);
    }
    Some(depths)
}

/// Canonical assignment: sorted by (length, symbol), incrementing, shifted left
/// at every length step. Written out longhand so it shares no code with the
/// table builder it is checking.
fn canonical_codes(lengths: &[u8]) -> Vec<(u32, u32)> {
    let max_len = u32::from(*lengths.iter().max().unwrap());
    let mut out = vec![(0u32, 0u32); lengths.len()];
    let mut code: u32 = 0;
    for l in 1..=max_len {
        for (sym, &len) in lengths.iter().enumerate() {
            if u32::from(len) == l {
                out[sym] = (code, l);
                code += 1;
            }
        }
        code <<= 1;
    }
    out
}

fn write_bits(out: &mut Vec<u8>, bit_pos: &mut usize, code: u32, len: u32) {
    for k in (0..len).rev() {
        let bit = ((code >> k) & 1) as u8;
        let idx = *bit_pos / 8;
        while idx >= out.len() {
            out.push(0);
        }
        out[idx] |= bit << (7 - *bit_pos % 8);
        *bit_pos += 1;
    }
}

#[test]
fn random_canonical_tables_round_trip() {
    let mut rng = Rng(0x9E37_79B9_7F4A_7C15);
    let mut long_code_trials = 0;
    let mut trials = 0;
    for trial in 0..600 {
        let n = 2 + rng.below(60);
        let max_len = (2 + rng.below(19)) as u8; // bzip2 caps code lengths at 20
        let skew = trial % 2 == 0;
        let lengths = match random_lengths(&mut rng, n, max_len, skew) {
            Some(l) => l,
            None => continue,
        };
        let group = match Group::build(&lengths) {
            Ok(g) => g,
            Err(_) => continue,
        };
        trials += 1;
        if lengths.iter().any(|&l| u32::from(l) > huffman::PRIMARY_BITS) {
            long_code_trials += 1;
        }

        let codes = canonical_codes(&lengths);
        let seq: Vec<usize> = (0..64).map(|_| rng.below(n)).collect();
        let mut data = Vec::new();
        let mut bit_pos = 0usize;
        for &s in &seq {
            let (code, len) = codes[s];
            write_bits(&mut data, &mut bit_pos, code, len);
        }
        data.extend_from_slice(&[0u8; 8]);

        let mut reader = BitReader::new(&data, 0).unwrap();
        for &s in &seq {
            // decode() is the hot path and assumes the accumulator is full --
            // the real loop in decoder.rs refills the same way. Without this it
            // underflows nbits once fewer than pb bits are buffered.
            reader.refill().unwrap();
            let got = group.decode(&mut reader).unwrap();
            assert_eq!(got, (s as u32, codes[s].1), "symbol mismatch, lengths {lengths:?}");
        }
        assert_eq!(reader.bit_pos(), bit_pos as u64, "bit position, lengths {lengths:?}");
    }
    assert!(trials > 100, "only {trials} usable trials");
    assert!(
        long_code_trials > 50,
        "only {long_code_trials} trials exercised the long-code fallback"
    );
}
