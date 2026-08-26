# Smoke test for the shared library: lints all common RTL, runs the skid_buffer pyuvm test.
TOPLEVEL        := skid_buffer
VERILOG_SOURCES := rtl/skid_buffer.sv
LINT_SOURCES    := $(wildcard rtl/*.sv)
MODULE          := test_skid_buffer
TEST_DIR        := tb/tests
include Makefile.cocotb
