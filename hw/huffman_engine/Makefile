# huffman_engine — see hw/FLOW.md for targets. Placeholders until the RTL stage.
TOPLEVEL        := huffman_engine
VERILOG_SOURCES := $(wildcard rtl/*.sv) ../common/rtl/axi_lite_if.sv
MODULE          := test_huffman_engine,tests_random,tests_errors,tests_ctrl,tests_deflate,tests_cover
# Toggle coverage is measured over control signals; the wide datapath/counters/ROMs/storage
# (upper bits unreachable by construction — see docs/coverage_waivers.md) are excluded both by
# inline `verilator coverage_off` regions and this width cap. cov target only.
export COVERAGE_MAX_WIDTH := 4
include ../common/Makefile.cocotb
