// blk_mem_gen_0.v -- [BEFORE] FPGA side: Vivado-generated style, internally a vendor primitive
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
  RAMB36E1 #(
    .WIDTH(32), .DEPTH(1024), .READ_LATENCY(1), .WRITE_MODE("read_first")
  ) u_ramb36e1 (
    .clka(clka), .clkb(clkb), .wea(wea), .web(web),
    .addra(addra), .addrb(addrb), .dina(dina), .dinb(dinb),
    .douta(douta), .doutb(doutb)
  );
endmodule
