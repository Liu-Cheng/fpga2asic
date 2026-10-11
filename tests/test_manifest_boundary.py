from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fpga2asic.config import load_project_config
from fpga2asic.extractor import extract_design
from fpga2asic.manifest import DesignManifest
from fpga2asic.workflow import ProjectWorkspace


class ManifestBoundaryTests(unittest.TestCase):
    def test_ipverify_plans_from_manifest_without_rtl_project_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "temporary_source.v"
            source.write_text(
                """
module RAMB36E1(input clk, output q);
endmodule
module top(input clk, output q);
  RAMB36E1 u_ram(.clk(clk), .q(q));
endmodule
""",
                encoding="utf-8",
            )
            manifest_path = root / "import" / "design-manifest.json"
            extract_design([source], "top").save(manifest_path)
            source.unlink()

            config_path = root / "conversion.toml"
            config_path.write_text(
                """
[project]
name = "manifest_only"
design_manifest = "import/design-manifest.json"
build_dir = "build"
ip_patterns = ["^RAMB\\\\w*$"]

[verification]
manifests_dir = "verification/tasks"
""",
                encoding="utf-8",
            )
            project = load_project_config(config_path)
            self.assertEqual("", project.top)
            tasks = ProjectWorkspace(project).plan()
            self.assertEqual(1, len(tasks))
            self.assertEqual("RAMB36E1", tasks[0].module)

            loaded = DesignManifest.load(manifest_path)
            self.assertEqual("top", loaded.top)


if __name__ == "__main__":
    unittest.main()
