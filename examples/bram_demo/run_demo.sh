#!/usr/bin/env bash
# run_demo.sh —— 用同一个 Testbench 跑「转换前(FPGA)」与「转换后(ASIC)」两套实现，比较行为是否一致
set -e
cd "$(dirname "$0")"
IV="${IVERILOG:-$HOME/.local/bin/iverilog}"
VV="${VVP:-$HOME/.local/bin/vvp}"
[ -x "$IV" ] || IV=iverilog
[ -x "$VV" ] || VV=vvp
mkdir -p build

echo "== 编译【转换前 · FPGA 侧】(厂商原语路径) =="
$IV -g2005 -s tb_bram -DTRACE_FILE='"build/trace_fpga.txt"' -o build/fpga_sim \
    fpga/vendor_prim_stub.v fpga/blk_mem_gen_0.v tb/tb_bram.v
$VV build/fpga_sim > build/fpga_sim.log

echo "== 编译【转换后 · ASIC 侧】(兼容 Wrapper + 可移植模型) =="
$IV -g2005 -s tb_bram -DTRACE_FILE='"build/trace_asic.txt"' -o build/asic_sim \
    asic/portable_true_dual_port_ram.v asic/blk_mem_gen_0.v tb/tb_bram.v
$VV build/asic_sim > build/asic_sim.log

echo "== 比较两份 trace =="
if diff -u build/trace_fpga.txt build/trace_asic.txt > build/trace.diff; then
  echo "✅ 行为一致：两份 trace 完全相同（$(wc -l < build/trace_fpga.txt) 行）"
  echo "   证据文件：build/trace_fpga.txt / build/trace_asic.txt"
else
  echo "❌ 存在差异（前 20 行）："; head -20 build/trace.diff; exit 1
fi
