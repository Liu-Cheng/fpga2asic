from __future__ import annotations

from pathlib import Path

from .manifest import DesignManifest
from .verilog import build_hierarchy, parse_verilog_files


def extract_design(source_files: list[Path], top: str) -> DesignManifest:
    """Reference RTL extractor.

    IP verification never imports this module. An existing repository can replace this
    implementation by producing the same DesignManifest JSON contract.
    """
    modules = parse_verilog_files(source_files)
    hierarchy = build_hierarchy(modules, top)
    return DesignManifest(
        top=top,
        source_files=source_files,
        modules=modules,
        hierarchy=hierarchy,
    )

