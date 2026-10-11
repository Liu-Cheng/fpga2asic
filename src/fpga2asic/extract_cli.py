from __future__ import annotations

import argparse
import sys

from .config import ConfigError, load_project_config
from .extractor import extract_design
from .manifest import ManifestError
from .verilog import VerilogParseError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rtl-manifest",
        description="Extract an RTL hierarchy manifest without creating conversion tasks",
    )
    parser.add_argument("-c", "--config", default="project.toml", help="Project TOML/JSON file")
    parser.add_argument("-o", "--output", help="Override design manifest output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project = load_project_config(args.config)
        if not project.top:
            raise ConfigError("[project].top is required by rtl-manifest")
        source_files = project.source_files()
        if not source_files:
            raise ManifestError("No Verilog/SystemVerilog sources matched the project configuration")
        manifest = extract_design(source_files, project.top)
        output = project.design_manifest if not args.output else project.root / args.output
        output = output.resolve()
        manifest.save(output)
        print(f"Extracted {len(manifest.modules)} modules")
        print(output)
        return 0
    except (ConfigError, ManifestError, VerilogParseError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
