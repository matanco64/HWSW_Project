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
//! Any operation reordering breaks bit-identity: SIMD-ing the ten pairs,
//! fusing multiply-add, reassociating the squared-distance sum, or hoisting
//! `mass * dt` out of the step loop all change the rounding and therefore the
//! trajectory (by ~1e-14 relative in the reported energy after 20,000 steps --
//! physically nothing, but no longer bit-identical).  Those transforms are
//! available and are worth roughly another 5-15%; take them only if the
//! report is willing to state a tolerance instead of "bit-for-bit".

use pyo3::prelude::*;

/// Simulation state: 3N positions, 3N velocities, N masses, and the fixed
/// pair schedule, all resident on the Rust side.
#[pyclass]
pub struct System {
    pos: Vec<f64>,
    vel: Vec<f64>,
    mass: Vec<f64>,
    pairs: Vec<(usize, usize)>,
}

#[pymethods]
impl System {
    /// Build from the benchmark's `SYSTEM` list: [(pos3, vel3, mass), ...].
    #[new]
    fn new(bodies: Vec<(Vec<f64>, Vec<f64>, f64)>) -> PyResult<Self> {
        let n = bodies.len();
        let mut pos = Vec::with_capacity(3 * n);
        let mut vel = Vec::with_capacity(3 * n);
        let mut mass = Vec::with_capacity(n);
        for (r, v, m) in bodies {
            if r.len() != 3 || v.len() != 3 {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "each body needs a 3-vector position and velocity",
                ));
            }
            pos.extend_from_slice(&r);
            vel.extend_from_slice(&v);
            mass.push(m);
        }
        // Same order as the benchmark's combinations(): (0,1)(0,2)...(n-2,n-1)
        let mut pairs = Vec::with_capacity(n * n / 2);
        for i in 0..n {
            for j in (i + 1)..n {
                pairs.push((i, j));
            }
        }
        Ok(System { pos, vel, mass, pairs })
    }

    /// `n` symplectic-Euler steps.  Mirrors `advance(dt, n)` exactly.
    fn advance(&mut self, dt: f64, n: u64) {
        let System { pos, vel, mass, pairs } = self;
        for _ in 0..n {
            for &(i, j) in pairs.iter() {
                let (a, b) = (3 * i, 3 * j);
                let dx = pos[a] - pos[b];
                let dy = pos[a + 1] - pos[b + 1];
                let dz = pos[a + 2] - pos[b + 2];
                let mag = dt * (dx * dx + dy * dy + dz * dz).powf(-1.5);
                let b1m = mass[i] * mag;
                let b2m = mass[j] * mag;
                vel[a] -= dx * b2m;
                vel[a + 1] -= dy * b2m;
                vel[a + 2] -= dz * b2m;
                vel[b] += dx * b1m;
                vel[b + 1] += dy * b1m;
                vel[b + 2] += dz * b1m;
            }
            for k in 0..pos.len() {
                pos[k] += dt * vel[k];
            }
        }
    }

    /// Mirrors `report_energy()`, including its `** 0.5` and `/ 2.`.
    fn energy(&self) -> f64 {
        let mut e = 0.0f64;
        for &(i, j) in self.pairs.iter() {
            let (a, b) = (3 * i, 3 * j);
            let dx = self.pos[a] - self.pos[b];
            let dy = self.pos[a + 1] - self.pos[b + 1];
            let dz = self.pos[a + 2] - self.pos[b + 2];
            e -= (self.mass[i] * self.mass[j])
                / (dx * dx + dy * dy + dz * dz).powf(0.5);
        }
        for i in 0..self.mass.len() {
            let a = 3 * i;
            let (vx, vy, vz) = (self.vel[a], self.vel[a + 1], self.vel[a + 2]);
            e += self.mass[i] * (vx * vx + vy * vy + vz * vz) / 2.0;
        }
        e
    }

    /// Mirrors `offset_momentum(ref)`; `r` is the reference body index.
    fn offset_momentum(&mut self, r: usize) {
        let (mut px, mut py, mut pz) = (0.0f64, 0.0f64, 0.0f64);
        for i in 0..self.mass.len() {
            let a = 3 * i;
            px -= self.vel[a] * self.mass[i];
            py -= self.vel[a + 1] * self.mass[i];
            pz -= self.vel[a + 2] * self.mass[i];
        }
        let a = 3 * r;
        self.vel[a] = px / self.mass[r];
        self.vel[a + 1] = py / self.mass[r];
        self.vel[a + 2] = pz / self.mass[r];
    }

    /// Read the state back out: (positions 3N, velocities 3N, masses N).
    fn state(&self) -> (Vec<f64>, Vec<f64>, Vec<f64>) {
        (self.pos.clone(), self.vel.clone(), self.mass.clone())
    }
}

#[pymodule]
fn nbody_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<System>()?;
    Ok(())
}
