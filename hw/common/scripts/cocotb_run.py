#!/usr/bin/env python3
"""Generic cocotb 2.0 runner used by hw/common/Makefile.cocotb `make sim`.

Builds with Verilator (default) or Icarus via cocotb_tools.runner, then runs the
Python test module. Coverage (Verilator --coverage) and FST waves are switches.
"""
import argparse
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sim", default="verilator")
    p.add_argument("--toplevel", required=True)
    p.add_argument("--module", required=True)
    p.add_argument("--build-dir", default="sim_build")
    p.add_argument("--waves", type=int, default=0)
    p.add_argument("--cov", type=int, default=0)
    p.add_argument("--testcase", default=None)
    p.add_argument("--seed", default=None)
    p.add_argument("--include", action="append", default=[])
    p.add_argument("sources", nargs="+")
    a = p.parse_args()

    sources = [Path(s) for s in a.sources]
    build_args = []
    if a.sim == "verilator":
        build_args += ["-Wno-fatal", "--timing", "--assert"]  # arm SVAs in regression (rcp/sqrt II guards)
        if a.cov:
            build_args += ["--coverage"]
        # Waves: runner adds --trace (VCD -> sim_build/dump.vcd). Native --trace-fst needs liblz4-dev
        # headers, which plain Ubuntu lacks; `make waves` converts VCD -> FST with vcd2fst instead.
        if a.waves:
            build_args += ["--trace-structs"]
    elif a.sim == "icarus":
        build_args += ["-g2012"]

    runner = get_runner(a.sim)
    runner.build(
        sources=sources,
        hdl_toplevel=a.toplevel,
        includes=[Path(i) for i in a.include],
        build_dir=a.build_dir,
        build_args=build_args,
        waves=bool(a.waves),
        timescale=("1ns", "1ps"),
        always=True,
    )
    kwargs = {}
    if a.testcase:
        kwargs["testcase"] = a.testcase
    if a.seed:
        kwargs["seed"] = int(a.seed)
    results = runner.test(
        hdl_toplevel=a.toplevel,
        test_module=a.module,
        build_dir=a.build_dir,
        test_dir=a.build_dir,
        waves=bool(a.waves),
        results_xml=os.path.abspath("results.xml"),
        **kwargs,
    )
    # cocotb 2.0 returns the results.xml path; parse it to set the exit code.
    import xml.etree.ElementTree as ET

    tree = ET.parse(str(results))
    total = failed = 0
    for tc in tree.iter("testcase"):
        total += 1
        if tc.find("failure") is not None or tc.find("error") is not None:
            failed += 1
            print(f"FAIL {tc.get('classname')}.{tc.get('name')}")
    print(f"sim: {total - failed}/{total} tests passed ({a.sim})")
    return 1 if failed or total == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
