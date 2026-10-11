#!/usr/bin/env bash
# run_demo.sh — run the "before (FPGA)" and "after (ASIC)" implementations with the same testbench
# and compare whether their behavior is identical
set -e
cd "$(dirname "$0")"
IV="${IVERILOG:-$HOME/.local/bin/iverilog}"
VV="${VVP:-$HOME/.local/bin/vvp}"
[ -x "$IV" ] || IV=iverilog
[ -x "$VV" ] || VV=vvp
mkdir -p build

echo "== Build [BEFORE - FPGA side] (vendor primitive path) =="
$IV -g2005 -s tb_bram -DTRACE_FILE='"build/trace_fpga.txt"' -o build/fpga_sim \
    fpga/vendor_prim_stub.v fpga/blk_mem_gen_0.v tb/tb_bram.v
$VV build/fpga_sim > build/fpga_sim.log

echo "== Build [AFTER  - ASIC side] (compatible wrapper + portable model) =="
$IV -g2005 -s tb_bram -DTRACE_FILE='"build/trace_asic.txt"' -o build/asic_sim \
    asic/portable_true_dual_port_ram.v asic/blk_mem_gen_0.v tb/tb_bram.v
$VV build/asic_sim > build/asic_sim.log

echo "== Compare the two traces =="
if diff -u build/trace_fpga.txt build/trace_asic.txt > build/trace.diff; then
  echo "PASS: identical behavior - both traces are byte-identical ($(wc -l < build/trace_fpga.txt) lines)"
else
  echo "FAIL: differences found (first 20 lines):"; head -20 build/trace.diff; exit 1
fi
