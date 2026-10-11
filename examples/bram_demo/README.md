# bram_demo — minimal runnable "behavior identical before/after" example for fpga2asic

**Purpose**: demonstrate the fpga2asic replacement idea and prove **on a local machine (iverilog, no
Xilinx/VCS required)** that the "before — FPGA side" and the "after — ASIC side" are **behaviorally
identical**.

## Layout

```
fpga/                        BEFORE (FPGA side)
  vendor_prim_stub.v         behaviorally equivalent subset stub for RAMB36E1 (local demo only;
                             in production this comes from the Xilinx simulation libraries)
  blk_mem_gen_0.v            Vivado-generated style: instantiates the vendor primitive
asic/                        AFTER (ASIC side)
  portable_true_dual_port_ram.v   portable behavioral model (no vendor dependency, ASIC synthesizable)
  blk_mem_gen_0.v                 compatible wrapper (same name and ports as the original module,
                                  so the upper level / TB needs no change)
tb/tb_bram.v                 common testbench (shared by both implementations, unchanged)
run_demo.sh                  build both + run + compare traces
build/                       artifacts (trace_fpga.txt / trace_asic.txt / trace.diff / logs)
```

## Run

```bash
./run_demo.sh
```

Expected output:

```
== Build [BEFORE - FPGA side] (vendor primitive path) ==
== Build [AFTER  - ASIC side] (compatible wrapper + portable model) ==
== Compare the two traces ==
PASS: identical behavior - both traces are byte-identical (29 lines)
```

## Semantic points covered by the TB

1. Full-word write + 1-cycle read latency
2. **read-first** (writing an address reads the *old* value in the same cycle)
3. **byte enable** partial writes
4. Independent dual-port reads
5. Write on port B → read on port A (cross-port visibility)

## Notes and boundaries

- `vendor_prim_stub.v` is a **behaviorally equivalent subset stub**, only so the demo can run on a
  machine without the Xilinx simulation libraries. **Production verification** should replace `fpga/`
  with the Vivado-generated IP simulation model, run the reference on the Xilinx simulator and the
  replacement implementation on VCS (see sections 8–9 of the design plan).
- The comparison in this demo is a **line-by-line diff of trace text**; the production flow uses
  **signal-level cycle-exact comparison** (transaction-level comparison for AXI).
- Simultaneous writes to the same address from both ports is undefined behavior (Xilinx yields `x`);
  this demo does not construct that scenario, and the replacement model does not invent a determined
  value for it either.
