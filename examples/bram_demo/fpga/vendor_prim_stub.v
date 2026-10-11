// vendor_prim_stub.v —— **仅用于本机演示**
// 真实的 RAMB36E1 由 Xilinx 仿真库（Vivado 生成）提供；这里写一个行为等价的
// 子集 stub，使本 demo 能在 iverilog 下跑通"转换前后一致"的流程。
module RAMB36E1 #(
  parameter integer WIDTH = 32,
  parameter integer DEPTH = 1024,
  parameter integer READ_LATENCY = 1,
  parameter         WRITE_MODE = "read_first"
)(
  input  wire        clka,
  input  wire        clkb,
  input  wire [3:0]  wea,
  input  wire [3:0]  web,
  input  wire [9:0]  addra,
  input  wire [9:0]  addrb,
  input  wire [31:0] dina,
  input  wire [31:0] dinb,
  output reg  [31:0] douta,
  output reg  [31:0] doutb
);
  reg [31:0] mem [0:DEPTH-1];

  always @(posedge clka) begin
    if (wea[0]) mem[addra][ 7: 0] <= dina[ 7: 0];
    if (wea[1]) mem[addra][15: 8] <= dina[15: 8];
    if (wea[2]) mem[addra][23:16] <= dina[23:16];
    if (wea[3]) mem[addra][31:24] <= dina[31:24];
    douta <= mem[addra];          // 非阻塞 → read-first
  end

  always @(posedge clkb) begin
    if (web[0]) mem[addrb][ 7: 0] <= dinb[ 7: 0];
    if (web[1]) mem[addrb][15: 8] <= dinb[15: 8];
    if (web[2]) mem[addrb][23:16] <= dinb[23:16];
    if (web[3]) mem[addrb][31:24] <= dinb[31:24];
    doutb <= mem[addrb];
  end
endmodule
