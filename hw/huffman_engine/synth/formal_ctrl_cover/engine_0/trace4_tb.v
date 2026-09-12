`ifndef VERILATOR
module testbench;
  reg [4095:0] vcdfile;
  reg clock;
`else
module testbench(input clock, output reg genclock);
  initial genclock = 1;
`endif
  reg genclock = 1;
  reg [31:0] cycle = 0;
  reg [0:0] PI_eob_sent_i;
  reg [0:0] PI_build_done_i;
  reg [0:0] PI_rst_n;
  reg [0:0] PI_mode_deflate_i;
  reg [0:0] PI_out_empty_i;
  reg [0:0] PI_doorbell_i;
  reg [0:0] PI_eob_i;
  reg [0:0] PI_stall_i;
  reg [0:0] PI_c0_valid_i;
  reg [0:0] PI_skip_done_i;
  reg [0:0] PI_underrun_i;
  reg [0:0] PI_err_symbol_i;
  reg [0:0] PI_abort_i;
  wire [0:0] PI_clk = clock;
  reg [0:0] PI_err_sel_i;
  reg [0:0] PI_err_table_i;
  reg [0:0] PI_limit_hit_i;
  reg [0:0] PI_nocode_i;
  reg [0:0] PI_sel_drained_i;
  ctrl_arcs UUT (
    .eob_sent_i(PI_eob_sent_i),
    .build_done_i(PI_build_done_i),
    .rst_n(PI_rst_n),
    .mode_deflate_i(PI_mode_deflate_i),
    .out_empty_i(PI_out_empty_i),
    .doorbell_i(PI_doorbell_i),
    .eob_i(PI_eob_i),
    .stall_i(PI_stall_i),
    .c0_valid_i(PI_c0_valid_i),
    .skip_done_i(PI_skip_done_i),
    .underrun_i(PI_underrun_i),
    .err_symbol_i(PI_err_symbol_i),
    .abort_i(PI_abort_i),
    .clk(PI_clk),
    .err_sel_i(PI_err_sel_i),
    .err_table_i(PI_err_table_i),
    .limit_hit_i(PI_limit_hit_i),
    .nocode_i(PI_nocode_i),
    .sel_drained_i(PI_sel_drained_i)
  );
`ifndef VERILATOR
  initial begin
    if ($value$plusargs("vcd=%s", vcdfile)) begin
      $dumpfile(vcdfile);
      $dumpvars(0, testbench);
    end
    #5 clock = 0;
    while (genclock) begin
      #5 clock = 0;
      #5 clock = 1;
    end
  end
`endif
  initial begin
`ifndef VERILATOR
    #1;
`endif
    // UUT.$auto$async2sync.\cc:107:execute$769  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$755  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$761  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$767  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$773  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$779  = 1'b1;
    UUT.dut.abort_pend = 1'b0;
    UUT.dut.aborted_set_o = 1'b0;
    UUT.dut.done_set_o = 1'b0;
    UUT.dut.err_set_o = 6'b000000;
    UUT.dut.start_pulse_o = 1'b0;
    UUT.dut.state = 3'b000;

    // state 0
    PI_eob_sent_i = 1'b0;
    PI_build_done_i = 1'b0;
    PI_rst_n = 1'b0;
    PI_mode_deflate_i = 1'b0;
    PI_out_empty_i = 1'b0;
    PI_doorbell_i = 1'b0;
    PI_eob_i = 1'b0;
    PI_stall_i = 1'b0;
    PI_c0_valid_i = 1'b0;
    PI_skip_done_i = 1'b0;
    PI_underrun_i = 1'b0;
    PI_err_symbol_i = 1'b0;
    PI_abort_i = 1'b0;
    PI_err_sel_i = 1'b0;
    PI_err_table_i = 1'b0;
    PI_limit_hit_i = 1'b0;
    PI_nocode_i = 1'b0;
    PI_sel_drained_i = 1'b0;
  end
  always @(posedge clock) begin
    // state 1
    if (cycle == 0) begin
      PI_eob_sent_i <= 1'b0;
      PI_build_done_i <= 1'b0;
      PI_rst_n <= 1'b1;
      PI_mode_deflate_i <= 1'b0;
      PI_out_empty_i <= 1'b0;
      PI_doorbell_i <= 1'b1;
      PI_eob_i <= 1'b0;
      PI_stall_i <= 1'b0;
      PI_c0_valid_i <= 1'b0;
      PI_skip_done_i <= 1'b0;
      PI_underrun_i <= 1'b0;
      PI_err_symbol_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_err_sel_i <= 1'b0;
      PI_err_table_i <= 1'b0;
      PI_limit_hit_i <= 1'b0;
      PI_nocode_i <= 1'b0;
      PI_sel_drained_i <= 1'b0;
    end

    // state 2
    if (cycle == 1) begin
      PI_eob_sent_i <= 1'b0;
      PI_build_done_i <= 1'b1;
      PI_rst_n <= 1'b1;
      PI_mode_deflate_i <= 1'b0;
      PI_out_empty_i <= 1'b0;
      PI_doorbell_i <= 1'b0;
      PI_eob_i <= 1'b0;
      PI_stall_i <= 1'b0;
      PI_c0_valid_i <= 1'b0;
      PI_skip_done_i <= 1'b1;
      PI_underrun_i <= 1'b0;
      PI_err_symbol_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_err_sel_i <= 1'b0;
      PI_err_table_i <= 1'b0;
      PI_limit_hit_i <= 1'b0;
      PI_nocode_i <= 1'b0;
      PI_sel_drained_i <= 1'b0;
    end

    // state 3
    if (cycle == 2) begin
      PI_eob_sent_i <= 1'b0;
      PI_build_done_i <= 1'b1;
      PI_rst_n <= 1'b1;
      PI_mode_deflate_i <= 1'b0;
      PI_out_empty_i <= 1'b0;
      PI_doorbell_i <= 1'b1;
      PI_eob_i <= 1'b1;
      PI_stall_i <= 1'b0;
      PI_c0_valid_i <= 1'b1;
      PI_skip_done_i <= 1'b1;
      PI_underrun_i <= 1'b1;
      PI_err_symbol_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_err_sel_i <= 1'b0;
      PI_err_table_i <= 1'b0;
      PI_limit_hit_i <= 1'b0;
      PI_nocode_i <= 1'b0;
      PI_sel_drained_i <= 1'b0;
    end

    // state 4
    if (cycle == 3) begin
      PI_eob_sent_i <= 1'b1;
      PI_build_done_i <= 1'b1;
      PI_rst_n <= 1'b1;
      PI_mode_deflate_i <= 1'b0;
      PI_out_empty_i <= 1'b1;
      PI_doorbell_i <= 1'b0;
      PI_eob_i <= 1'b0;
      PI_stall_i <= 1'b0;
      PI_c0_valid_i <= 1'b0;
      PI_skip_done_i <= 1'b1;
      PI_underrun_i <= 1'b0;
      PI_err_symbol_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_err_sel_i <= 1'b0;
      PI_err_table_i <= 1'b0;
      PI_limit_hit_i <= 1'b0;
      PI_nocode_i <= 1'b0;
      PI_sel_drained_i <= 1'b1;
    end

    // state 5
    if (cycle == 4) begin
      PI_eob_sent_i <= 1'b0;
      PI_build_done_i <= 1'b0;
      PI_rst_n <= 1'b1;
      PI_mode_deflate_i <= 1'b0;
      PI_out_empty_i <= 1'b0;
      PI_doorbell_i <= 1'b0;
      PI_eob_i <= 1'b0;
      PI_stall_i <= 1'b0;
      PI_c0_valid_i <= 1'b0;
      PI_skip_done_i <= 1'b0;
      PI_underrun_i <= 1'b0;
      PI_err_symbol_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_err_sel_i <= 1'b0;
      PI_err_table_i <= 1'b0;
      PI_limit_hit_i <= 1'b0;
      PI_nocode_i <= 1'b0;
      PI_sel_drained_i <= 1'b0;
    end

    // state 6
    if (cycle == 5) begin
      PI_eob_sent_i <= 1'b0;
      PI_build_done_i <= 1'b0;
      PI_rst_n <= 1'b0;
      PI_mode_deflate_i <= 1'b0;
      PI_out_empty_i <= 1'b0;
      PI_doorbell_i <= 1'b0;
      PI_eob_i <= 1'b0;
      PI_stall_i <= 1'b0;
      PI_c0_valid_i <= 1'b0;
      PI_skip_done_i <= 1'b0;
      PI_underrun_i <= 1'b0;
      PI_err_symbol_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_err_sel_i <= 1'b0;
      PI_err_table_i <= 1'b0;
      PI_limit_hit_i <= 1'b0;
      PI_nocode_i <= 1'b0;
      PI_sel_drained_i <= 1'b0;
    end

    genclock <= cycle < 6;
    cycle <= cycle + 1;
  end
endmodule
