#!/usr/bin/env bash
set -euo pipefail

top=${1:?top module is required}
test_name=${2:?test name is required}
seed=${3:?seed is required}
trace_file=${4:?trace file is required}
filelist=${5:-filelist.f}
include_dirs=${6:-include_dirs.txt}

: "${VCS_BIN:=vcs}"

include_args=()
if [[ -f "$include_dirs" ]]; then
  while IFS= read -r include_dir; do
    [[ -n "$include_dir" ]] && include_args+=("+incdir+$include_dir")
  done < "$include_dirs"
fi

"$VCS_BIN" -full64 -sverilog "${include_args[@]}" -f "$filelist" -top "$top" -o simv ${VCS_COMPILE_ARGS:-}
./simv \
  "+TEST=$test_name" \
  "+ntb_random_seed=$seed" \
  "+TRACE_FILE=$trace_file" \
  ${VCS_RUN_ARGS:-} 2>&1 | tee simv.log

test -f "$trace_file"
