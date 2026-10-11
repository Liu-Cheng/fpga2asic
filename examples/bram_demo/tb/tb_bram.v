// tb_bram.v —— 【公共 Testbench】转换前后共用，一行不改
// 覆盖：全字写、读延迟(1)、read-first、byte enable 部分写、双端口读、B 口写后 A 口读
`timescale 1ns/1ps
`ifndef TRACE_FILE
  `define TRACE_FILE "trace.txt"
`endif

module tb_bram;
  reg clk = 0;
  always #5 clk = ~clk;

  reg  [9:0]  addra = 0, addrb = 0;
  reg  [31:0] dina  = 0, dinb  = 0;
  reg  [3:0]  wea   = 0, web   = 0;
  wire [31:0] douta, doutb;
  integer fd, i;

  blk_mem_gen_0 dut (
    .clka(clk), .clkb(clk), .wea(wea), .web(web),
    .addra(addra), .addrb(addrb), .dina(dina), .dinb(dinb),
    .douta(douta), .doutb(doutb)
  );

  task step; begin @(posedge clk); #1; end endtask

  initial begin
    fd = $fopen(`TRACE_FILE, "w");

    // ① A 口全字写 16 个地址
    for (i = 0; i < 16; i = i + 1) begin
      addra = i[9:0]; dina = 32'hA0000000 + i; wea = 4'hF; step;
    end
    wea = 0; addra = 0; step;
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    // ② A 口顺序读回（验证 1 周期延迟）
    for (i = 0; i < 16; i = i + 1) begin
      addra = i[9:0]; step;
      $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);
    end

    // ③ read-first：addr=5 写新值，同一拍读出的应是旧值
    addra = 10'd5; dina = 32'hDEADBEEF; wea = 4'hF; step;   // 本拍 douta=旧值
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);
    wea = 0; step;                                          // 下一拍读到新值
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    // ④ byte enable 部分写：只改低 2 字节
    addra = 10'd6; dina = 32'h0000FFFF; wea = 4'b0011; step;
    wea = 0; step;
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    // ⑤ B 口读若干地址（双端口独立读）
    for (i = 0; i < 8; i = i + 1) begin
      addrb = i[9:0]; step;
      $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);
    end

    // ⑥ B 口写 addr=100，再由 A 口读（跨端口可见）
    addrb = 10'd100; dinb = 32'h5A5A1234; web = 4'hF; step;
    web = 0;
    addra = 10'd100; step; step;
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    $fclose(fd);
    $display("trace written: %0s", `TRACE_FILE);
    $finish;
  end
endmodule
