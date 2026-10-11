# fpga2asic

A verification-driven **FPGA digital IP replacement** tool (MVP).

The codebase is deliberately split into two independent capabilities:

- **RTL extractor** — emits only a standard *design manifest*.
- **IP verification tool** — only consumes that manifest, plans replacement tasks, and submits the
  original FPGA RTL and the replacement Verilog to **Xilinx** and **VCS** simulation servers respectively.

```text
existing RTL submodule extractor   or   rtl-manifest
                 │
                 ▼
        design-manifest.json
                 │
                 ▼
   ipverify: task planning and remote verification
```

`ipverify` never calls an RTL parser. Any existing repository that already extracts submodules can
completely replace the lightweight `rtl-manifest` shipped here, as long as it emits the data defined by
`schemas/design-manifest.schema.json`.

**This version includes:**

- A standalone Verilog module/instance hierarchy extraction command.
- A versioned `design-manifest.json` interface.
- Configurable FPGA IP recognition rules.
- Bottom-up replacement tasks with persistent state.
- Testbench manifest admission checks.
- A local executor and an SSH/SCP-based remote executor.
- Configurable Xilinx/VCS commands, environment variables, server addresses, and tool paths.
- Simulation input packaging, remote execution, and trace/log retrieval.
- Signal-level cycle-exact comparison and AXI transaction-level comparison.
- A Markdown project report.

## Quick start

The project depends only on the Python 3.11+ standard library.

**Step 1 — generate the design manifest with the standalone extractor:**

```bash
rtl-manifest -c project.toml
```

If an existing repository already performs submodule extraction, skip this step and have it emit the
file referenced by the `design_manifest` configuration key.

**Step 2 — let the verification tool consume the manifest:**

```bash
ipverify -c project.toml plan
ipverify -c project.toml list
ipverify -c project.toml check-tb
ipverify -c project.toml run
ipverify -c project.toml report
```

To work from the `src` tree, install the development version first:

```bash
python -m pip install -e .
```

Or run it without installing:

```bash
export PYTHONPATH=src          # Linux/macOS
set PYTHONPATH=src             # Windows
python -m fpga2asic.extract_cli -c project.toml
python -m fpga2asic -c project.toml plan
```

## Example: BRAM replacement (behavioral equivalence before/after)

A **minimal, runnable** example that shows what the tool does: replace an FPGA-specific IP
(Xilinx Block RAM) with **vendor-neutral, ASIC-synthesizable** behavioral Verilog while keeping the
behavior identical.

### The core idea

```text
FPGA side: the design instantiates blk_mem_gen_0  →  internally a RAMB36E1 primitive (not ASIC synthesizable)
                    │ replace
                    ▼
ASIC side: generate a compatible wrapper with the SAME module name and ports → instantiating a portable behavioral model
```

- **Module name and ports are preserved** → the upper-level RTL, the testbench, and scripts need **no changes at all**.
- The internals are swapped for a behavioral implementation → **no vendor dependency, synthesizable for ASIC**.
- **Externally visible timing is preserved** (read latency, read-first semantics, etc.).

### Before / after

**Before** (`examples/bram_demo/fpga/blk_mem_gen_0.v`) — internally a vendor primitive:

```verilog
module blk_mem_gen_0 ( /* same ports */ );
  RAMB36E1 #(
    .WIDTH(32), .DEPTH(1024), .READ_LATENCY(1), .WRITE_MODE("read_first")
  ) u_ramb36e1 (
    .clka(clka), .clkb(clkb), .wea(wea), .web(web),
    .addra(addra), .addrb(addrb), .dina(dina), .dinb(dinb),
    .douta(douta), .doutb(doutb)
  );
endmodule
```

**After** (`examples/bram_demo/asic/blk_mem_gen_0.v`) — same name and ports, portable model inside:

```verilog
module blk_mem_gen_0 ( /* same ports */ );
  portable_true_dual_port_ram #(
    .WIDTH(32), .DEPTH(1024), .ADDR_W(10),
    .READ_LATENCY(1), .WRITE_MODE("read_first")
  ) u_impl (
    .clk_a(clka), .we_a(wea), .addr_a(addra), .din_a(dina), .dout_a(douta),
    .clk_b(clkb), .we_b(web), .addr_b(addrb), .din_b(dinb), .dout_b(doutb)
  );
endmodule
```

### Running the example

Requires `iverilog` / `vvp` (Icarus Verilog). **No Xilinx or VCS installation is needed.**

```bash
cd examples/bram_demo
./run_demo.sh
```

Expected output:

```
== Build [BEFORE - FPGA side] (vendor primitive path) ==
== Build [AFTER  - ASIC side] (compatible wrapper + portable model) ==
== Compare the two traces ==
PASS: identical behavior - both traces are byte-identical (29 lines)
```

### Semantics covered by the example

| # | Semantic point | Why it matters |
|---|---|---|
| 1 | Full-word write + **1-cycle read latency** | A latency mismatch breaks the upper-level timing |
| 2 | **read-first** (when writing an address, the same cycle reads the *old* value) | Read-after-write semantics are the most common IP-replacement pitfall |
| 3 | **Byte-enable** partial writes | Partial writes must not overwrite the whole word |
| 4 | Independent dual-port reads | Both ports must share the same memory array |
| 5 | Write on port B → read on port A (cross-port visibility) | Consistency between ports |

See [`examples/bram_demo/README.md`](examples/bram_demo/README.md) for details and the boundary statement.

> ⚠️ The `RAMB36E1` used in the example is a **behaviorally equivalent subset stub**, only so the flow
> can run on a machine without the Xilinx simulation libraries. Production verification should use the
> **Vivado-generated IP simulation model** (reference implementation on the Xilinx simulator, replacement
> implementation on VCS) with **signal-level cycle-exact comparison** (transaction-level for AXI interfaces).

## Remote server configuration

See `examples/project.remote.toml`. Xilinx and VCS can live on different servers:

```toml
[servers.xilinx_server]
type = "ssh"
host = "192.0.2.10"
user = "eda"
work_root = "/data/fpga2asic/jobs"

[servers.asic_server]
type = "ssh"
host = "192.0.2.20"
user = "eda"
work_root = "/data/fpga2asic/jobs"
```

Tool commands, software paths, and environment variables are configured independently:

```toml
[tools.xilinx]
server = "xilinx_server"
command = "bash tool/0000_run_xsim.sh {top} {test} {seed} {trace} {filelist} {include_dirs}"
support_files = ["scripts/remote/run_xsim.sh"]

[tools.xilinx.environment]
XILINX_XVLOG = "/opt/Xilinx/Vivado/bin/xvlog"
```

SSH login should use keys with `BatchMode=yes`. When a remote run fails, the server-side working
directory is kept by default and the report points to its location so you can log in and investigate.

## Interface boundary between the two capabilities

### RTL extraction

**Input:** RTL source files, top module, include directories, and macro definitions.

**Output:** `design-manifest.json` containing module definitions, instance relationships, source file
locations, and the full hierarchy tree. It does **not** recognize IP to be replaced, does not create
verification tasks, and does not invoke simulators.

### IP replacement verification

**Input:** `design-manifest.json`, IP recognition rules, testbench manifests, and remote server configuration.

**Output:** the replacement task DAG, Xilinx/VCS simulation results, comparison results, and the project
report. It does **not** read or parse RTL to rebuild the hierarchy.

The JSON Schema for the interface lives in `schemas/design-manifest.schema.json`.

## Testbench manifest

After running `ipverify plan`, every task gets a `.toml.example`. Copy it to `.toml` and fill in the
common testbench, the original FPGA files, and the ASIC replacement files:

```toml
module = "blk_mem_gen_0"
top = "tb_top"
comparison = "signal"
trace_file = "trace.jsonl"
tests = ["basic_read_write", "collision"]
seeds = [1, 17, 2026]

common_files = [
  "verification/blk_mem_gen_0/tb_top.sv",
  "verification/common/trace_writer.sv",
]
fpga_files = ["vivado/ip/blk_mem_gen_0.v"]
asic_files = ["replacements/blk_mem_gen_0.v"]
```

For AXI modules, set `comparison` to `axi_transaction`. The testbench monitor should emit completed,
normalized AXI transactions; the comparator ignores legal cycle differences but checks data, address,
ID, response, and the ordering within each ID.

## Trace format

Signal-level comparison is exact, item by item and field by field:

```json
{"cycle": 10, "valid": 1, "data": "0000002a"}
```

Example AXI transaction record:

```json
{"event":"write","cycle":42,"id":3,"addr":"00001000","data":"12345678","strb":"f","resp":0}
```

AXI comparison ignores time fields such as `cycle` and `time`, and compares each transaction type and
ID while preserving their respective ordering.

## Current MVP boundaries

The bundled `rtl-manifest` is a lightweight hierarchy scanner: good enough to bootstrap the flow and to
handle regular module instantiations. Complex macros, deep `generate` blocks, interfaces, and full
SystemVerilog elaboration should be handled by an existing submodule extractor, Surelog/UHDM, or another
proper front end. The remote verification capability depends only on the standard design manifest and not
on the bundled front end.

## Documentation

- Design plan (19 sections): [`docs/design-plan.md`](docs/design-plan.md)
- License: [MIT](LICENSE)
