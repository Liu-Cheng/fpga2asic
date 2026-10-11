// blk_mem_gen_0.v —— 【转换后】兼容 Wrapper：与原模块同名同端口 → 上层 RTL / Testbench 不用改
module blk_mem_gen_0 (
  input  wire        clka,
  input  wire        clkb,
  input  wire [3:0]  wea,
  input  wire [3:0]  web,
  input  wire [9:0]  addra,
  input  wire [9:0]  addrb,
  input  wire [31:0] dina,
  input  wire [31:0] dinb,
  output wire [31:0] douta,
  output wire [31:0] doutb
);
  portable_true_dual_port_ram #(
    .WIDTH(32), .DEPTH(1024), .ADDR_W(10), .READ_LATENCY(1), .WRITE_MODE("read_first")
  ) u_impl (
    .clk_a(clka), .we_a(wea), .addr_a(addra), .din_a(dina), .dout_a(douta),
    .clk_b(clkb), .we_b(web), .addr_b(addrb), .din_b(dinb), .dout_b(doutb)
  );
endmodule
