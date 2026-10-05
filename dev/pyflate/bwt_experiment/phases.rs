use std::time::Instant;
#[inline(never)] fn count1(l: &[u8]) -> [u32; 256] { let mut c = [0u32; 256]; for &s in l { c[s as usize] += 1; } c }
#[inline(never)] fn count4(l: &[u8]) -> [u32; 256] {
    let mut c = [[0u32; 256]; 4]; let ch = l.chunks_exact(4);
    let r = ch.remainder(); for w in ch { c[0][w[0] as usize] += 1; c[1][w[1] as usize] += 1; c[2][w[2] as usize] += 1; c[3][w[3] as usize] += 1; }
    for &s in r { c[0][s as usize] += 1; }
    let mut o = [0u32; 256]; for s in 0..256 { o[s] = c[0][s] + c[1][s] + c[2][s] + c[3][s]; } o }
fn starts(c: [u32; 256]) -> [u32; 256] { let mut b = [0u32; 256]; let mut t = 0; for s in 0..256 { b[s] = t; t += c[s]; } b }
#[inline(never)] fn build2(l: &[u8], mut base: [u32; 256], p: &mut [u32], q: &mut [u32]) { for (i, &s) in l.iter().enumerate() { let b = &mut base[s as usize]; p[*b as usize] = ((i as u32) << 8) | s as u32; q[i] = (*b << 8) | s as u32; *b += 1; } }
#[inline(never)] fn walk2(p: &[u32], q: &[u32], end: usize, out: &mut [u8]) { let n = out.len(); let (mut xf, mut xb) = (end as u32, end as u32); let (mut lo, mut hi) = (0, n);
    while lo < n / 2 { let vf = p[xf as usize]; let vb = q[xb as usize]; out[lo] = vf as u8; xf = vf >> 8; hi -= 1; out[hi] = vb as u8; xb = vb >> 8; lo += 1; }
    while hi > lo { let vb = q[xb as usize]; hi -= 1; out[hi] = vb as u8; xb = vb >> 8; } }
// Two steps per lookup.  p2[x] = (next2 << 16) | (c1 << 8) | c2 for the forward chain,
// q2[x] the same for the backward chain.  Built from p/q with independent loads.
#[inline(never)] fn build_x2(p: &[u32], q: &[u32], p2: &mut [u64], q2: &mut [u64]) {
    for x in 0..p.len() { let a = p[x]; let b = p[(a >> 8) as usize]; p2[x] = ((b >> 8) as u64) << 16 | ((a & 255) as u64) << 8 | (b & 255) as u64;
                          let a = q[x]; let b = q[(a >> 8) as usize]; q2[x] = ((b >> 8) as u64) << 16 | ((a & 255) as u64) << 8 | (b & 255) as u64; } }
#[inline(never)] fn walk_x2(p2: &[u64], q: &[u32], q2: &[u64], end: usize, out: &mut [u8]) {
    let n = out.len(); let (mut xf, mut xb) = (end, end); let (mut lo, mut hi) = (0usize, n);
    while hi - lo >= 4 { let vf = p2[xf]; let vb = q2[xb];
        out[lo] = (vf >> 8) as u8; out[lo + 1] = vf as u8; xf = (vf >> 16) as usize; lo += 2;
        out[hi - 1] = (vb >> 8) as u8; out[hi - 2] = vb as u8; xb = (vb >> 16) as usize; hi -= 2; }
    while hi > lo { let vb = q[xb]; hi -= 1; out[hi] = vb as u8; xb = (vb >> 8) as usize; } }
fn best<F: FnMut()>(mut f: F) -> f64 { let mut m = u128::MAX; for _ in 0..200 { let t = Instant::now(); f(); m = m.min(t.elapsed().as_nanos()); } m as f64 / 1e6 }
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let l = std::fs::read(&a[1]).unwrap(); let end: usize = a[2].parse().unwrap(); let n = l.len();
    assert_eq!(count1(&l), count4(&l));
    let base = starts(count4(&l));
    let (mut p, mut q, mut out) = (vec![0u32; n], vec![0u32; n], vec![0u8; n]);
    let (mut p2, mut q2) = (vec![0u64; n], vec![0u64; n]);
    let c1 = best(|| { std::hint::black_box(count1(&l)); }); let c4 = best(|| { std::hint::black_box(count4(&l)); });
    let b = best(|| build2(&l, base, &mut p, &mut q));
    let w = best(|| walk2(&p, &q, end, &mut out)); let ref_out = out.clone();
    let bx = best(|| build_x2(&p, &q, &mut p2, &mut q2));
    let wx = best(|| walk_x2(&p2, &q, &q2, end, &mut out)); assert_eq!(ref_out, out);
    println!("n={n}: histogram 1-way {c1:.3} 4-way {c4:.3} | build {b:.3} | 2 chains walk {w:.3} | x2 tables: extra build {bx:.3} walk {wx:.3} (walk+extra {:.3}) | best total {:.3}",
        bx + wx, c4 + b + w.min(bx + wx));
}
