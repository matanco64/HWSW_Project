#!/bin/bash
# Experiment run on the course VM. Leaves the system-installed (submitted)
# pyflate_rs untouched: the experimental build is loaded via PYTHONPATH only.
set -eo pipefail
cd /tmp/bwt_exp
export PATH=$HOME/.cargo/bin:$PATH
B=benchmarks/bm_pyflate; X=dev/pyflate/bwt_experiment; SITE=/tmp/bwt_exp/site
echo "=== ENV"; date -u; python3 -V; lscpu | grep "Model name"; git_rev=$(cat REV); echo "branch rev $git_rev"
echo "=== BUILD"
(cd rust/pyflate && CARGO_TARGET_DIR=/tmp/bwt_exp/target python3 -m maturin build --release -i python3 -o /tmp/bwt_exp/wheels 2>&1 | tail -1)
rm -rf $SITE && mkdir -p $SITE && python3 -m zipfile -e wheels/pyflate_rs-*.whl $SITE
PYTHONPATH=$SITE python3 -c "import pyflate_rs as p; print('experimental:', p.__file__, hasattr(p,'bwt_rle4'))"
python3 -c "import pyflate_rs as p; print('system (submitted):', p.__file__, hasattr(p,'bwt_rle4'))"
echo "=== CHECK"; PYTHONPATH=$SITE taskset -c 0 python3 $X/bwt_check.py $B
echo "=== STAGES submitted (system pyflate_rs, Python inverse BWT)"; taskset -c 0 python3 $X/stages.py $B 20
echo "=== STAGES experiment"; PYTHONPATH=$SITE taskset -c 0 python3 $X/stages.py $B 20
echo "=== KERNELS"; PYTHONPATH=$SITE taskset -c 0 python3 $X/bwt_time.py $B
echo "=== PHASES"; mkdir -p phases && PYTHONPATH=$SITE python3 $X/dump.py $B phases > phases/ends.txt
rustc -O $X/phases.rs -o phases/phases; while read k e; do taskset -c 0 phases/phases phases/$k.L $e; done < phases/ends.txt
echo "=== PYPERF"
rm -f pf_*.json
taskset -c 0 python3 $B/run_benchmark.py -q -o pf_submitted.json
HWSW_BWT=rust PYTHONPATH=$SITE taskset -c 0 python3 $B/run_benchmark.py --inherit-environ HWSW_BWT,PYTHONPATH -q -o pf_experiment.json
python3 -m pyperf compare_to pf_submitted.json pf_experiment.json --table
python3 -m pyperf dump pf_experiment.json | grep -i -E "pyflate_rs|backend" | head -5
echo ALL_DONE
