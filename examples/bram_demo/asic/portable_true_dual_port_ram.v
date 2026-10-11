// portable_true_dual_port_ram.v -- [AFTER] portable behavioral model (no vendor dependency,
//                                 ASIC synthesizable)
module portable_true_dual_port_ram #(
  parameter integer WIDTH = 32,
  parameter integer DEPTH = 1024,
  parameter integer ADDR_W = 10,
  parameter integer READ_LATENCY = 1,
  parameter         WRITE_MODE = "read_first"
)(
  input  wire             clk_a,
  input  wire [WIDTH/8-1:0] we_a,
  input  wire [ADDR_W-1:0]  addr_a,
  input  wire [WIDTH-1:0]   din_a,
  output reg  [WIDTH-1:0]   dout_a,
  input  wire             clk_b,
  input  wire [WIDTH/8-1:0] we_b,
  input  wire [ADDR_W-1:0]  addr_b,
  input  wire [WIDTH-1:0]   din_b,
  output reg  [WIDTH-1:0]   dout_b
);
  // Parameter legality checks (design plan section 10.1, "parameter constraints and illegal
  // combination checks")
  initial begin
      if (WIDTH % 8 != 0)            $display("ERROR: WIDTH must be multiple of 8");
      if (READ_LATENCY != 1)         $display("ERROR: only READ_LATENCY=1 supported");
      if (WRITE_MODE != "read_first") $display("ERROR: only WRITE_MODE=read_first supported");
  end

  reg [WIDTH-1:0] mem [0:DEPTH-1];

  always @(posedge clk_a) begin
    if (we_a[0]) mem[addr_a][ 7: 0] <= din_a[ 7: 0];
    if (we_a[1]) mem[addr_a][15: 8] <= din_a[15: 8];
    if (we_a[2]) mem[addr_a][23:16] <= din_a[23:16];
    if (we_a[3]) mem[addr_a][31:24] <= din_a[31:24];
    dout_a <= mem[addr_a];        // non-blocking -> read-first (reads the old value on a same-address write)
  end

  always @(posedge clk_b) begin
    if (we_b[0]) mem[addr_b][ 7: 0] <= din_b[ 7: 0];
    if (we_b[1]) mem[addr_b][15: 8] <= din_b[15: 8];
    if (we_b[2]) mem[addr_b][23:16] <= din_b[23:16];
    if (we_b[3]) mem[addr_b][31:24] <= din_b[31:24];
    dout_b <= mem[addr_b];
  end
endmodule
