# fpga2asic

这是一个验证驱动的 FPGA 数字 IP 替换工具 MVP。代码明确分为两个独立功能：RTL 提取器只输出标准设计清单，IP 验证工具只读取该清单、生成替换任务，并把原始 FPGA RTL 和替代 Verilog 分别提交到 Xilinx、VCS 仿真服务器。

```text
已有RTL子模块提取器 或 rtl-manifest
                 │
                 ▼
       design-manifest.json
                 │
                 ▼
      ipverify：任务规划与远程验证
```

`ipverify` 不调用 RTL 解析器。将来已有 repo 的子模块提取代码只要输出 `schemas/design-manifest.schema.json` 定义的数据，就可以完全替换本项目附带的轻量 `rtl-manifest`。

当前版本包含：

- 独立的 Verilog 模块与实例层次提取命令。
- 版本化的 `design-manifest.json` 接口。
- 可配置的 FPGA IP 识别规则。
- 自底向上的替换任务和持久化状态。
- Testbench manifest 准入检查。
- 本地执行器和基于 SSH/SCP 的远程执行器。
- 可配置 Xilinx/VCS 命令、环境变量、服务器 IP 和软件路径。
- 仿真输入打包、远程执行、trace 与日志回传。
- 信号级周期精确比较和 AXI 事务级比较。
- Markdown 项目报告。

## 快速开始

本项目只依赖 Python 3.11 或更高版本的标准库。

第一步由独立提取器生成设计清单：

```bash
rtl-manifest -c project.toml
```

如果已有 repo 已经完成子模块提取，可以跳过这一步，直接让它输出配置项 `design_manifest` 指向的文件。

第二步由验证工具读取清单：

```bash
ipverify -c project.toml plan
ipverify -c project.toml list
ipverify -c project.toml check-tb
ipverify -c project.toml run
ipverify -c project.toml report
```

源码位于 `src` 时，可先安装开发版本：

```bash
python -m pip install -e .
```

也可以不安装：

```bash
set PYTHONPATH=src
python -m fpga2asic.extract_cli -c project.toml
python -m fpga2asic -c project.toml plan
```

Linux/macOS 使用 `export PYTHONPATH=src`。

## 示例：BRAM 替换（转换前后行为一致）

用一个**最小可跑**的例子说明这套工具在做什么——把 FPGA 专用 IP（Xilinx Block RAM）
替换为**厂商无关、可 ASIC 综合**的行为级 Verilog，并保证行为一致。

### 核心思路

```
FPGA 侧：设计实例化 blk_mem_gen_0  → 内部是 RAMB36E1 原语（ASIC 不可综合）
                    │ 替换
                    ▼
ASIC 侧：生成【同名、同端口】的兼容 Wrapper → 内部接【可移植行为级模型】
```

- 保留**模块名与端口** → 上层 RTL、Testbench、脚本**一行都不用改**
- 内部换成行为级实现 → **无厂商依赖，可综合到 ASIC**
- 保持**对外可见时序**一致（读延迟、read-first 语义等）

### 代码对照

**转换前（`examples/bram_demo/fpga/blk_mem_gen_0.v`）**——内部走厂商原语：

```verilog
module blk_mem_gen_0 ( /* 端口同上 */ );
  RAMB36E1 #(
    .WIDTH(32), .DEPTH(1024), .READ_LATENCY(1), .WRITE_MODE("read_first")
  ) u_ramb36e1 (
    .clka(clka), .clkb(clkb), .wea(wea), .web(web),
    .addra(addra), .addrb(addrb), .dina(dina), .dinb(dinb),
    .douta(douta), .doutb(doutb)
  );
endmodule
```

**转换后（`examples/bram_demo/asic/blk_mem_gen_0.v`）**——同名同端口，内部换成可移植模型：

```verilog
module blk_mem_gen_0 ( /* 端口同上 */ );
  portable_true_dual_port_ram #(
    .WIDTH(32), .DEPTH(1024), .ADDR_W(10),
    .READ_LATENCY(1), .WRITE_MODE("read_first")
  ) u_impl (
    .clk_a(clka), .we_a(wea), .addr_a(addra), .din_a(dina), .dout_a(douta),
    .clk_b(clkb), .we_b(web), .addr_b(addrb), .din_b(dinb), .dout_b(doutb)
  );
endmodule
```

### 运行示例

依赖：`iverilog` / `vvp`（Icarus Verilog）。**无需 Xilinx 或 VCS。**

```bash
cd examples/bram_demo
./run_demo.sh
```

预期输出：

```
== 编译【转换前 · FPGA 侧】(厂商原语路径) ==
== 编译【转换后 · ASIC 侧】(兼容 Wrapper + 可移植模型) ==
== 比较两份 trace ==
✅ 行为一致：两份 trace 完全相同（29 行）
```

### 示例覆盖的语义点

| # | 语义点 | 为什么关键 |
|---|---|---|
| 1 | 全字写 + **1 周期读延迟** | 延迟不一致会破坏上层时序 |
| 2 | **read-first**（同地址写入时，同拍读出旧值） | 写后读语义是 IP 替换最常见的坑 |
| 3 | **byte enable** 部分写 | 分字节写不能整字覆盖 |
| 4 | 双端口独立读 | 两端口必须共享同一存储体 |
| 5 | B 口写 → A 口读（跨端口可见） | 端口间一致性 |

详细说明与边界声明见 [`examples/bram_demo/README.md`](examples/bram_demo/README.md)。

> ⚠️ 示例中的 `RAMB36E1` 是**行为等价子集 stub**，仅为在没有 Xilinx 仿真库的机器上跑通流程；
> 正式验证应换成 **Vivado 生成的 IP 仿真模型**（Xilinx 跑参考实现，VCS 跑替代实现），
> 并采用**信号级 cycle-exact 比较**（AXI 类接口用事务级比较）。

## 远程服务器配置

参考 `examples/project.remote.toml`。Xilinx 和 VCS 可以配置在不同服务器：

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

工具命令、软件路径和环境变量独立配置：

```toml
[tools.xilinx]
server = "xilinx_server"
command = "bash tool/0000_run_xsim.sh {top} {test} {seed} {trace} {filelist} {include_dirs}"
support_files = ["scripts/remote/run_xsim.sh"]

[tools.xilinx.environment]
XILINX_XVLOG = "/opt/Xilinx/Vivado/bin/xvlog"
```

SSH 登录建议使用密钥和 `BatchMode=yes`。远程执行失败时，服务器工作目录默认保留，报告会给出位置，便于登录服务器排查。

## 两个功能的接口边界

### RTL提取功能

输入：RTL源文件、顶层模块、include和宏配置。

输出：`design-manifest.json`，包括模块定义、实例关系、源文件位置和完整层次树。它不识别待替换IP，不创建验证任务，也不调用仿真器。

### IP替换验证功能

输入：`design-manifest.json`、IP识别规则、Testbench manifest和远程服务器配置。

输出：替换任务DAG、Xilinx/VCS仿真结果、比较结果和项目报告。它不读取或解析RTL来重建层次。

接口的JSON Schema位于 `schemas/design-manifest.schema.json`。

## Testbench manifest

运行 `ipverify plan` 后，每个任务都会生成一个 `.toml.example`。复制为 `.toml` 并填写公共 Testbench、原始 FPGA 文件和 ASIC 替代文件：

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

AXI 模块将 `comparison` 设置为 `axi_transaction`。Testbench monitor 应输出已经完成的标准化 AXI 事务；比较器忽略合法的周期差异，但检查数据、地址、ID、响应以及每个 ID 内的顺序。

## Trace 格式

信号级比较逐条、逐字段精确比较：

```json
{"cycle": 10, "valid": 1, "data": "0000002a"}
```

AXI 事务记录示例：

```json
{"event":"write","cycle":42,"id":3,"addr":"00001000","data":"12345678","strb":"f","resp":0}
```

AXI 比较会忽略 `cycle`、`time` 等时间字段，并按事务类型和 ID 保持各自的顺序进行比较。

## 当前 MVP 边界

附带的 `rtl-manifest` 是轻量级层次扫描器，适合建立流程和处理常规模块实例。复杂宏、深度 generate、interface 和完整 SystemVerilog elaboration 应由已有子模块提取器、Surelog/UHDM 或其他正式前端负责。远程验证功能只依赖标准设计清单，不依赖附带前端。
