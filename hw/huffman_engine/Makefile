# huffman_engine — see hw/FLOW.md for targets. Placeholders until the RTL stage.
TOPLEVEL        := huffman_engine
VERILOG_SOURCES := $(wildcard rtl/*.sv) ../common/rtl/axi_lite_if.sv
MODULE          := test_huffman_engine,tests_random,tests_errors,tests_ctrl,tests_deflate,tests_cover
include ../common/Makefile.cocotb
