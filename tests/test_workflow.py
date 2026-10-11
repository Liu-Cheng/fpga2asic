from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from fpga2asic.config import load_project_config
from fpga2asic.extractor import extract_design
from fpga2asic.models import TaskStatus
from fpga2asic.workflow import ProjectWorkspace


class WorkflowTests(unittest.TestCase):
    def test_local_mock_backends_complete_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "rtl").mkdir()
            (root / "verification" / "tasks").mkdir(parents=True)
            (root / "replacements").mkdir()
            (root / "tools").mkdir()
            (root / "rtl" / "design.v").write_text(
                """
module DSP48E1(input clk, input [7:0] a, output [15:0] q);
endmodule
module top(input clk, input [7:0] a, output [15:0] q);
  DSP48E1 u_dsp(.clk(clk), .a(a), .q(q));
endmodule
""",
                encoding="utf-8",
            )
            (root / "verification" / "tb_top.sv").write_text("module tb_top; endmodule\n", encoding="utf-8")
            (root / "replacements" / "DSP48E1.v").write_text(
                "module DSP48E1(input clk, input [7:0] a, output [15:0] q); assign q=a*a; endmodule\n",
                encoding="utf-8",
            )
            mock = root / "tools" / "mock_sim.py"
            mock.write_text(
                """
import json, sys
m = json.load(open(sys.argv[1], encoding='utf-8'))
with open(m['trace_file'], 'w', encoding='utf-8') as f:
    f.write(json.dumps({'cycle': 1, 'q': '0004'}) + '\\n')
""",
                encoding="utf-8",
            )
            python = Path(sys.executable).as_posix()
            config = root / "project.toml"
            config.write_text(
                f'''
[project]
name = "test"
top = "top"
sources = ["rtl/*.v"]
build_dir = "build"
ip_patterns = ["^DSP48\\\\w*$"]

[verification]
manifests_dir = "verification/tasks"

[servers.local]
type = "local"

[tools.xilinx]
server = "local"
command = "\\\"{python}\\\" src/project/tools/mock_sim.py {{manifest}}"
artifacts = ["trace.jsonl"]

[tools.vcs]
server = "local"
command = "\\\"{python}\\\" src/project/tools/mock_sim.py {{manifest}}"
artifacts = ["trace.jsonl"]
''',
                encoding="utf-8",
            )
            project = load_project_config(config)
            workspace = ProjectWorkspace(project)
            manifest = extract_design(project.source_files(), project.top)
            manifest.save(project.design_manifest)
            tasks = workspace.plan()
            self.assertEqual(1, len(tasks))
            task = tasks[0]
            (root / "verification" / "tasks" / f"{task.task_id}.toml").write_text(
                f'''
module = "DSP48E1"
top = "tb_top"
comparison = "signal"
trace_file = "trace.jsonl"
tests = ["basic"]
seeds = [1, 2]
common_files = ["verification/tb_top.sv", "tools/mock_sim.py"]
fpga_files = ["rtl/design.v"]
asic_files = ["replacements/DSP48E1.v"]
''',
                encoding="utf-8",
            )
            summary = workspace.run_replacement(task.task_id)
            self.assertEqual(TaskStatus.ACCEPTED, summary.task.status)
            self.assertEqual(2, len(summary.comparisons))
            for comparison in summary.comparisons:
                self.assertTrue(comparison.matched)


if __name__ == "__main__":
    unittest.main()
