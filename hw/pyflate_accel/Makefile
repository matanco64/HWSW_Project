# pyflate_accel — huffman_engine -> mtf_cam chain wrapper; integration check only (`make sim`).
TOPLEVEL        := pyflate_accel
# tb-only tops of huffman_engine are filtered out; both modules share ../common/rtl/axi_lite_if.sv.
VERILOG_SOURCES := rtl/pyflate_accel.sv \
                   $(filter-out %_tb_top.sv,$(wildcard ../huffman_engine/rtl/*.sv)) \
                   $(wildcard ../mtf_cam/rtl/*.sv) \
                   ../common/rtl/axi_lite_if.sv
MODULE          := test_chain
TEST_DIR        := tb
LINT_SOURCES    := rtl/pyflate_accel.sv
INCLUDE_DIRS    := ../common/rtl rtl ../huffman_engine/rtl ../mtf_cam/rtl
# The shared `sim` rule touches $(HW_ROOT)/.advisor/last_sim.txt (hw-flow stop-hook marker). This
# check is outside the hw-flow, so point that marker inside our own (gitignored) sim_build.
override HW_ROOT := $(CURDIR)/sim_build/.hwroot
include ../common/Makefile.cocotb
