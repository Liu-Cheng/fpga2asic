#!/usr/bin/env bash
set -euo pipefail

top=${1:?top module is required}
test_name=${2:?test name is required}
seed=${3:?seed is required}
trace_file=${4:?trace file is required}
filelist=${5:-filelist.f}
include_dirs=${6:-include_dirs.txt}

: "${XILINX_XVLOG:=xvlog}"
: "${XILINX_XELAB:=xelab}"
: "${XILINX_XSIM:=xsim}"

include_args=()
if [[ -f "$include_dirs" ]]; then
  while IFS= read -r include_dir; do
    [[ -n "$include_dir" ]] && include_args+=("-i" "$include_dir")
  done < "$include_dirs"
fi

"$XILINX_XVLOG" -sv "${include_args[@]}" -f "$filelist" ${XILINX_XVLOG_ARGS:-}
"$XILINX_XELAB" "$top" -s fpga2asic_snapshot ${XILINX_XELAB_ARGS:-}
"$XILINX_XSIM" fpga2asic_snapshot -runall \
  -testplusarg "TEST=$test_name" \
  -testplusarg "SEED=$seed" \
  -testplusarg "TRACE_FILE=$trace_file" \
  ${XILINX_XSIM_ARGS:-}

test -f "$trace_file"
