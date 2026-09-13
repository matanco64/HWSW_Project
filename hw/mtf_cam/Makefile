# mtf_cam — see hw/FLOW.md for targets. Stage 4 (hw-rtl): RTL under rtl/ + the shared AXI-Lite cell.
TOPLEVEL        := mtf_cam
VERILOG_SOURCES := $(wildcard rtl/*.sv) ../common/rtl/axi_lite_if.sv
MODULE          := test_mtf_cam
# `make formal` runs the SymbiYosys harness at synth/formal.sby (the shared FORMAL_SBY default):
# mtf_list list invariants F-05/K8 (prove/bmc/cover) + m_l AXIS handshake F-06 (hs/hscover). It uses
# the Yosys slang frontend (read_slang) so the harness can observe mtf_list internals -- see the .sby.
include ../common/Makefile.cocotb
