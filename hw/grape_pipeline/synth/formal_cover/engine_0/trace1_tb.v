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
  reg [0:0] PI_all_done_i;
  reg [0:0] PI_abort_i;
  reg [31:0] PI_nsteps_i;
  wire [0:0] PI_clk = clock;
  reg [0:0] PI_rst_n;
  reg [0:0] PI_doorbell_i;
  fsm_arcs UUT (
    .all_done_i(PI_all_done_i),
    .abort_i(PI_abort_i),
    .nsteps_i(PI_nsteps_i),
    .clk(PI_clk),
    .rst_n(PI_rst_n),
    .doorbell_i(PI_doorbell_i)
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
    // UUT.$auto$async2sync.\cc:107:execute$459  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$451  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$457  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$463  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$469  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$475  = 1'b1;
    UUT.dut.abort_pend = 1'b0;
    UUT.dut.cycles = 64'b0000000000000000000000000000000000000000000000000000000000000000;
    UUT.dut.state = 3'b000;
    UUT.dut.steps = 32'b00000000000000000000000000000000;

    // state 0
    PI_all_done_i = 1'b0;
    PI_abort_i = 1'b0;
    PI_nsteps_i = 32'b00000000000000000000000000000000;
    PI_rst_n = 1'b0;
    PI_doorbell_i = 1'b0;
  end
  always @(posedge clock) begin
    // state 1
    if (cycle == 0) begin
      PI_all_done_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_nsteps_i <= 32'b00000000000000000000000000000000;
      PI_rst_n <= 1'b1;
      PI_doorbell_i <= 1'b1;
    end

    // state 2
    if (cycle == 1) begin
      PI_all_done_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_nsteps_i <= 32'b10000000000000000000000000000000;
      PI_rst_n <= 1'b1;
      PI_doorbell_i <= 1'b0;
    end

    // state 3
    if (cycle == 2) begin
      PI_all_done_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_nsteps_i <= 32'b00000000000000000000000000000000;
      PI_rst_n <= 1'b1;
      PI_doorbell_i <= 1'b0;
    end

    // state 4
    if (cycle == 3) begin
      PI_all_done_i <= 1'b0;
      PI_abort_i <= 1'b0;
      PI_nsteps_i <= 32'b00000000000000000000000000000000;
      PI_rst_n <= 1'b0;
      PI_doorbell_i <= 1'b0;
    end

    genclock <= cycle < 4;
    cycle <= cycle + 1;
  end
endmodule
