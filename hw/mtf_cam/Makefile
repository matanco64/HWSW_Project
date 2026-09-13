# mtf_cam — see hw/FLOW.md for targets. Stage 4 (hw-rtl): RTL under rtl/ + the shared AXI-Lite cell.
TOPLEVEL        := mtf_cam
VERILOG_SOURCES := $(wildcard rtl/*.sv) ../common/rtl/axi_lite_if.sv
MODULE          := test_mtf_cam
# `make formal` runs the SymbiYosys harness at synth/formal.sby (the shared FORMAL_SBY default):
# mtf_list list invariants F-05/K8 (prove/bmc/cover) + m_l AXIS handshake F-06 (hs/hscover). It uses
# the Yosys slang frontend (read_slang) so the harness can observe mtf_list internals -- see the .sby.
include ../common/Makefile.cocotb

# `make area` (shared target) synthesizes the default W=8 build -> synth/area.txt.
# `make area-sweep` reproduces the PPA trade-off design points: Liberty-mapped area
# at W=4/8/16 (via chparam in the dedicated synth/yosys_area_w*.ys scripts) plus the
# non-flattened per-module attribution. Outputs synth/area_w{4,8,16}.txt and
# synth/area_permodule.txt. See docs/ppa.md.
.PHONY: area-sweep
area-sweep: area
	cp synth/area.txt synth/area_w8.txt
	$(YOSYS) -q -l synth/yosys_w4.log        -s synth/yosys_area_w4.ys
	$(YOSYS) -q -l synth/yosys_w16.log       -s synth/yosys_area_w16.ys
	$(YOSYS) -q -l synth/yosys_permodule.log -s synth/yosys_area_permodule.ys
	@for w in 4 8 16; do $(PYTHON) $(COMMON_DIR)/scripts/area_summary.py synth/area_w$$w.txt; done
