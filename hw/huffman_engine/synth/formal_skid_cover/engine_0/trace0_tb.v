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
  reg [0:0] PI_flush_i;
  reg [0:0] PI_m_sym_tready;
  wire [0:0] PI_clk = clock;
  reg [31:0] PI_push_data_i;
  reg [0:0] PI_push_last_i;
  reg [0:0] PI_push_i;
  reg [0:0] PI_rst_n;
  skid UUT (
    .flush_i(PI_flush_i),
    .m_sym_tready(PI_m_sym_tready),
    .clk(PI_clk),
    .push_data_i(PI_push_data_i),
    .push_last_i(PI_push_last_i),
    .push_i(PI_push_i),
    .rst_n(PI_rst_n)
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
    // UUT.$auto$async2sync.\cc:107:execute$190  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$188  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$194  = 1'b1;
    UUT.dut.slot0 = 33'b000000000000000000000000000000000;
    UUT.dut.slot1 = 33'b000000000000000000000000000000000;
    UUT.dut.v0 = 1'b0;
    UUT.dut.v1 = 1'b0;

    // state 0
    PI_flush_i = 1'b0;
    PI_m_sym_tready = 1'b0;
    PI_push_data_i = 32'b00000000000000000000000000000000;
    PI_push_last_i = 1'b0;
    PI_push_i = 1'b0;
    PI_rst_n = 1'b0;
  end
  always @(posedge clock) begin
    // state 1
    if (cycle == 0) begin
      PI_flush_i <= 1'b0;
      PI_m_sym_tready <= 1'b0;
      PI_push_data_i <= 32'b00000000000000000000000000000000;
      PI_push_last_i <= 1'b1;
      PI_push_i <= 1'b1;
      PI_rst_n <= 1'b1;
    end

    // state 2
    if (cycle == 1) begin
      PI_flush_i <= 1'b0;
      PI_m_sym_tready <= 1'b1;
      PI_push_data_i <= 32'b00000000000000000000000000000000;
      PI_push_last_i <= 1'b0;
      PI_push_i <= 1'b0;
      PI_rst_n <= 1'b1;
    end

    // state 3
    if (cycle == 2) begin
      PI_flush_i <= 1'b0;
      PI_m_sym_tready <= 1'b0;
      PI_push_data_i <= 32'b00000000000000000000000000000000;
      PI_push_last_i <= 1'b0;
      PI_push_i <= 1'b0;
      PI_rst_n <= 1'b0;
    end

    genclock <= cycle < 3;
    cycle <= cycle + 1;
  end
endmodule
