# mtf_cam — see hw/FLOW.md for targets. Stage 4 (hw-rtl): RTL under rtl/ + the shared AXI-Lite cell.
TOPLEVEL        := mtf_cam
VERILOG_SOURCES := $(wildcard rtl/*.sv) ../common/rtl/axi_lite_if.sv
MODULE          := test_mtf_cam
include ../common/Makefile.cocotb
