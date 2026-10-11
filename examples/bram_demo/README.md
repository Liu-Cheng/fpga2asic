# bram_demo —— fpga2asic 转换前后「行为一致」最小可跑示例

**目的**：展示 fpga2asic 的替换思路，并**在本机（iverilog，不依赖 Xilinx/VCS）**验证
「转换前 FPGA 侧」与「转换后 ASIC 侧」**行为完全一致**。

## 目录

```
fpga/                        转换前（FPGA 侧）
  vendor_prim_stub.v         RAMB36E1 行为子集 stub（仅本机演示用；真实由 Xilinx 仿真库提供）
  blk_mem_gen_0.v            Vivado 生成风格：实例化厂商原语
asic/                        转换后（ASIC 侧）
  portable_true_dual_port_ram.v   可移植行为级模型（无厂商依赖，可 ASIC 综合）
  blk_mem_gen_0.v                 兼容 Wrapper（与原模块同名同端口 → 上层/TB 不用改）
tb/tb_bram.v                 公共 Testbench（两套实现共用，一行不改）
run_demo.sh                  编译两套 + 跑 + 比较 trace
build/                       产物（trace_fpga.txt / trace_asic.txt / trace.diff / 日志）
```

## 运行

```bash
./run_demo.sh
```

预期输出：`✅ 行为一致：两份 trace 完全相同（N 行）`

## TB 覆盖的语义点

1. 全字写 + 1 周期读延迟
2. **read-first**（同地址写入时，同拍读出旧值）
3. **byte enable** 部分写
4. 双端口独立读
5. B 口写 → A 口读（跨端口可见）

## 说明与边界

- `vendor_prim_stub.v` 是**行为等价的子集 stub**，只为让 demo 能在没有 Xilinx 仿真库的机器上跑通；
  **正式验证**应把 `fpga/` 替换为 Vivado 生成的 IP 仿真模型，在 Xilinx 仿真器跑参考、在 VCS 跑替代实现（对应开发方案第 8–9 节）。
- 比对方式在本 demo 里是「trace 文本逐行 diff」；正式流程用的是**信号级 cycle-exact 比较**（AXI 用事务级比较）。
- 同地址双端口同时写属未定义行为（Xilinx 会给 x），本 demo 不构造该场景，替代模型也不擅自给出确定值。
