// tb_bram.v -- [common testbench] shared before and after the replacement, unchanged
// Covers: full-word write, read latency (1), read-first, byte-enable partial write, dual-port read,
// and read on port A after a write on port B
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

    // (1) Full-word write to 16 addresses on port A
    for (i = 0; i < 16; i = i + 1) begin
      addra = i[9:0]; dina = 32'hA0000000 + i; wea = 4'hF; step;
    end
    wea = 0; addra = 0; step;
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    // (2) Sequential read-back on port A (verifies the 1-cycle latency)
    for (i = 0; i < 16; i = i + 1) begin
      addra = i[9:0]; step;
      $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);
    end

    // (3) read-first: write a new value to addr=5; the same cycle must read back the old value
    addra = 10'd5; dina = 32'hDEADBEEF; wea = 4'hF; step;   // douta = old value in this cycle
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);
    wea = 0; step;                                          // next cycle reads the new value
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    // (4) byte-enable partial write: modify only the low 2 bytes
    addra = 10'd6; dina = 32'h0000FFFF; wea = 4'b0011; step;
    wea = 0; step;
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    // (5) Read several addresses on port B (independent dual-port reads)
    for (i = 0; i < 8; i = i + 1) begin
      addrb = i[9:0]; step;
      $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);
    end

    // (6) Write addr=100 on port B, then read it on port A (cross-port visibility)
    addrb = 10'd100; dinb = 32'h5A5A1234; web = 4'hF; step;
    web = 0;
    addra = 10'd100; step; step;
    $fwrite(fd, "T=%0t A=%h B=%h\n", $time, douta, doutb);

    $fclose(fd);
    $display("trace written: %0s", `TRACE_FILE);
    $finish;
  end
endmodule
