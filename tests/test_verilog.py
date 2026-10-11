from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fpga2asic.extractor import extract_design
from fpga2asic.planner import build_replacement_tasks


class VerilogAnalysisTests(unittest.TestCase):
    def test_builds_bottom_up_ip_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "design.v"
            source.write_text(
                """
module RAMB36E1(input clk, input d, output q);
endmodule

module blk_mem_gen_0(input clk, input d, output q);
  RAMB36E1 u_primitive(.clk(clk), .d(d), .q(q));
endmodule

module top(input clk, input d, output q);
  blk_mem_gen_0 u_mem(.clk(clk), .d(d), .q(q));
endmodule
""",
                encoding="utf-8",
            )
            manifest = extract_design([source], "top")
            replacement_tasks = build_replacement_tasks(
                manifest.hierarchy, (r"^RAMB\w*$", r"^blk_mem_gen\w*$")
            )
            self.assertEqual(3, len(manifest.modules))
            self.assertEqual(2, len(replacement_tasks))
            tasks = {task.module: task for task in replacement_tasks}
            self.assertEqual([tasks["RAMB36E1"].task_id], tasks["blk_mem_gen_0"].dependencies)
            self.assertEqual([], tasks["RAMB36E1"].dependencies)


if __name__ == "__main__":
    unittest.main()
