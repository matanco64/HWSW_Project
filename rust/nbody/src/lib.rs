//! Native `advance()` for the pyperformance `nbody` benchmark.
//!
//! Boundary design: ONE FFI crossing per `advance()` call.  The simulation
//! state lives Rust-side in a `#[pyclass] System`; Python holds an opaque
//! handle.  A benchmark iteration is
//!
//!     sys.advance(0.01, 20000)          # 1 crossing, 200,000 pair updates
//!     sys.write_back(SYSTEM)            # 1 crossing, 35 floats out
//!
//! so the per-crossing cost (~25-60 ns for a PyO3 call plus argument
//! conversion) is amortised over 20,000 integration steps.  Marshalling the
//! full state every call would also be fine here -- 5 bodies x 7 f64 = 280
//! bytes -- but keeping it resident makes the accelerator analogy exact: the
//! `#[pyclass]` is the device's register file, `advance()` is the doorbell,
//! `write_back()` is the read-back window.
//!
//! DATA LAYOUT.  There is deliberately no `Body` struct: positions, velocities
//! and masses live in three separate arrays (SoA), so each hot loop walks the
//! streams it needs and never loads a field it does not use.  What *is*
//! grouped is the x/y/z of a single vector, in `Vec3` -- a `repr(C)` triple of
//! `f64` whose memory image is byte-identical to the three consecutive slots
//! of the flat `Vec<f64>` it replaces.  `Vec<Vec3>` is therefore the same
//! bytes as the old `pos`/`vel` arrays, with the index arithmetic
//! (`3 * i + 2`) moved into the type system.
//!
//! FLOATING-POINT CONTRACT.  Every arithmetic expression below is written to
//! mirror the Python source operation for operation, in the same order and
//! with the same associativity, so that the 35-float state after 20,000 steps
//! is expected to compare bit-for-bit equal to the stock benchmark's.  That
//! rests on three things, all of which must hold and be *verified*, never
//! assumed:
//!   1. `f64::powf(-1.5)` lowers to a call to the platform `pow`, which on
//!      x86_64-unknown-linux-gnu is the same glibc `__ieee754_pow` that
//!      CPython's `float_pow` calls.  Same input, same routine, same result.
//!   2. Rust does not contract `a*b + c` into an FMA and does not reassociate
//!      float sums (no `-ffp-contract=fast`, no fast-math).  LLVM will
//!      therefore not auto-vectorise the `dx*dx + dy*dy + dz*dz` reduction.
//!   3. `Cargo.toml` does not turn any of that off.  See the note there.
//!
//! The `Vec3` operators are componentwise and `#[inline(always)]`, so they
//! expand to exactly the scalar expressions the flat-array version spelled out
//! by hand: same operations, same order, no extra rounding.
//!
//! Any operation reordering breaks bit-identity: SIMD-ing the ten pairs,
//! fusing multiply-add, reassociating the squared-distance sum, or hoisting
//! `mass * dt` out of the step loop all change the rounding and therefore the
//! trajectory (by ~1e-14 relative in the reported energy after 20,000 steps --
//! physically nothing, but no longer bit-identical).  Those transforms are
//! available and are worth roughly another 5-15%; take them only if the
//! report is willing to state a tolerance instead of "bit-for-bit".

use std::ops::{AddAssign, Div, Mul, Sub, SubAssign};

use pyo3::prelude::*;

/// One 3-vector of the simulation: a position, a velocity, or a momentum.
///
/// `repr(C)` pins the layout to three consecutive `f64`s, so `[Vec3]` and an
/// `[f64]` of three times the length are the same bytes.  This is a name for
/// the flat array's index arithmetic, not a change of data layout.
#[derive(Clone, Copy, Debug, PartialEq)]
#[repr(C)]
pub struct Vec3 {
    x: f64,
    y: f64,
    z: f64,
}

impl Vec3 {
    const ZERO: Vec3 = Vec3 { x: 0.0, y: 0.0, z: 0.0 };

    /// `x*x + y*y + z*z`, summed left to right -- the exact expression, and
    /// association, of the Python `dx*dx + dy*dy + dz*dz`.
    #[inline(always)]
    fn norm_squared(self) -> f64 {
        self.x * self.x + self.y * self.y + self.z * self.z
    }
}

impl Sub for Vec3 {
    type Output = Vec3;
    #[inline(always)]
    fn sub(self, rhs: Vec3) -> Vec3 {
        Vec3 { x: self.x - rhs.x, y: self.y - rhs.y, z: self.z - rhs.z }
    }
}

impl Mul<f64> for Vec3 {
    type Output = Vec3;
    #[inline(always)]
    fn mul(self, s: f64) -> Vec3 {
        Vec3 { x: self.x * s, y: self.y * s, z: self.z * s }
    }
}

/// Scalar on the left, so `dt * v` can be written the way Python writes it.
impl Mul<Vec3> for f64 {
    type Output = Vec3;
    #[inline(always)]
    fn mul(self, v: Vec3) -> Vec3 {
        Vec3 { x: self * v.x, y: self * v.y, z: self * v.z }
    }
}

impl Div<f64> for Vec3 {
    type Output = Vec3;
    #[inline(always)]
    fn div(self, s: f64) -> Vec3 {
        Vec3 { x: self.x / s, y: self.y / s, z: self.z / s }
    }
}

impl AddAssign for Vec3 {
    #[inline(always)]
    fn add_assign(&mut self, rhs: Vec3) {
        self.x += rhs.x;
        self.y += rhs.y;
        self.z += rhs.z;
    }
}

impl SubAssign for Vec3 {
    #[inline(always)]
    fn sub_assign(&mut self, rhs: Vec3) {
        self.x -= rhs.x;
        self.y -= rhs.y;
        self.z -= rhs.z;
    }
}

/// A body-index pair, in the order the benchmark's `combinations()` yields
/// them: (0,1) (0,2) ... (n-2,n-1).
type Pair = (usize, usize);

/// Simulation state: N positions, N velocities, N masses, and the fixed pair
/// schedule, all resident on the Rust side.
#[pyclass]
pub struct System {
    pos: Vec<Vec3>,
    vel: Vec<Vec3>,
    mass: Vec<f64>,
    pairs: Vec<Pair>,
}

#[pymethods]
impl System {
    /// Build from the benchmark's `SYSTEM` list: [(pos3, vel3, mass), ...].
    #[new]
    fn new(bodies: Vec<(Vec<f64>, Vec<f64>, f64)>) -> PyResult<Self> {
        let n = bodies.len();
        let mut pos = Vec::with_capacity(n);
        let mut vel = Vec::with_capacity(n);
        let mut mass = Vec::with_capacity(n);
        for (r, v, m) in bodies {
            pos.push(vec3_from_slice(&r)?);
            vel.push(vec3_from_slice(&v)?);
            mass.push(m);
        }
        Ok(System { pos, vel, mass, pairs: pair_schedule(n) })
    }

    /// `n` symplectic-Euler steps.  Mirrors `advance(dt, n)` exactly.
    fn advance(&mut self, dt: f64, n: u64) {
        // Destructured so `kick` can hold `&[Vec3]` and `&mut [Vec3]` at once.
        let System { pos, vel, mass, pairs } = self;
        for _ in 0..n {
            kick(pos, vel, mass, pairs, dt);
            drift(pos, vel, dt);
        }
    }

    /// Mirrors `report_energy()`, including its `** 0.5` and `/ 2.`.
    fn energy(&self) -> f64 {
        self.add_kinetic_energy(self.potential_energy())
    }

    /// Mirrors `offset_momentum(ref)`; `r` is the reference body index.
    fn offset_momentum(&mut self, r: usize) {
        let mut p = Vec3::ZERO;
        for i in 0..self.mass.len() {
            p -= self.vel[i] * self.mass[i];
        }
        self.vel[r] = p / self.mass[r];
    }

    /// Read the state back out: (positions 3N, velocities 3N, masses N).
    fn state(&self) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        (flatten(&self.pos), flatten(&self.vel), self.mass.clone())
    }
}

impl System {
    /// `-sum_{i<j} m_i m_j / |r_i - r_j|`, pairs in schedule order.
    fn potential_energy(&self) -> f64 {
        let mut e = 0.0f64;
        for &(i, j) in self.pairs.iter() {
            let d = self.pos[i] - self.pos[j];
            e -= (self.mass[i] * self.mass[j]) / d.norm_squared().powf(0.5);
        }
        e
    }

    /// Adds `sum_i m_i |v_i|^2 / 2`, bodies in index order, into `e`.
    ///
    /// It folds into the running total instead of returning its own sum on
    /// purpose: `report_energy()` adds the kinetic terms into the accumulator
    /// that already holds the potential energy, and float addition is not
    /// associative, so a separately summed `potential + kinetic` can differ in
    /// the last bit.
    fn add_kinetic_energy(&self, mut e: f64) -> f64 {
        for i in 0..self.mass.len() {
            e += self.mass[i] * self.vel[i].norm_squared() / 2.0;
        }
        e
    }
}

/// Velocity half of the step: the pairwise gravitational impulse.
///
/// The hot loop -- 10 pairs x 20,000 steps per benchmark iteration.  Keep it
/// scalar and in this order; see the FLOATING-POINT CONTRACT above.
#[inline]
fn kick(pos: &[Vec3], vel: &mut [Vec3], mass: &[f64], pairs: &[Pair], dt: f64) {
    for &(i, j) in pairs.iter() {
        let d = pos[i] - pos[j];
        let mag = dt * d.norm_squared().powf(-1.5);
        let mi_mag = mass[i] * mag;
        let mj_mag = mass[j] * mag;
        vel[i] -= d * mj_mag;
        vel[j] += d * mi_mag;
    }
}

/// Position half of the step: straight-line motion at the updated velocity.
#[inline]
fn drift(pos: &mut [Vec3], vel: &[Vec3], dt: f64) {
    for i in 0..pos.len() {
        pos[i] += dt * vel[i];
    }
}

/// All (i, j) with i < j, in the benchmark's `combinations()` order.
fn pair_schedule(n: usize) -> Vec<Pair> {
    let mut pairs = Vec::with_capacity(n * n / 2);
    for i in 0..n {
        for j in (i + 1)..n {
            pairs.push((i, j));
        }
    }
    pairs
}

fn vec3_from_slice(v: &[f64]) -> PyResult<Vec3> {
    match v {
        [x, y, z] => Ok(Vec3 { x: *x, y: *y, z: *z }),
        _ => Err(pyo3::exceptions::PyValueError::new_err(
            "each body needs a 3-vector position and velocity",
        )),
    }
}

/// N vectors -> the flat 3N list Python expects back.
fn flatten(vs: &[Vec3]) -> Vec<f64> {
    let mut out = Vec::with_capacity(3 * vs.len());
    for v in vs {
        out.extend_from_slice(&[v.x, v.y, v.z]);
    }
    out
}

#[pymodule]
fn nbody_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<System>()?;
    Ok(())
}
