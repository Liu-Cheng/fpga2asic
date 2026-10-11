from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TaskStatus(StrEnum):
    DISCOVERED = "discovered"
    BLOCKED_NO_TB = "blocked_no_tb"
    TB_READY = "tb_ready"
    FPGA_BASELINE_RUNNING = "fpga_baseline_running"
    FPGA_BASELINE_PASS = "fpga_baseline_pass"
    FPGA_BASELINE_FAIL = "fpga_baseline_fail"
    REPLACEMENT_READY = "replacement_ready"
    ASIC_SIM_RUNNING = "asic_sim_running"
    ASIC_SIM_PASS = "asic_sim_pass"
    ASIC_SIM_FAIL = "asic_sim_fail"
    COMPARE_PASS = "compare_pass"
    COMPARE_FAIL = "compare_fail"
    ACCEPTED = "accepted"
    MANUAL_REQUIRED = "manual_required"


class ComparisonMode(StrEnum):
    SIGNAL = "signal"
    AXI_TRANSACTION = "axi_transaction"


@dataclass(slots=True)
class Instance:
    module: str
    name: str
    parameters: str = ""
    ports: str = ""
    source_line: int = 0


@dataclass(slots=True)
class ModuleDefinition:
    name: str
    source: Path
    start_line: int
    instances: list[Instance] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = str(self.source)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleDefinition":
        return cls(
            name=data["name"],
            source=Path(data["source"]),
            start_line=int(data["start_line"]),
            instances=[Instance(**item) for item in data.get("instances", [])],
        )


@dataclass(slots=True)
class HierarchyNode:
    path: str
    module: str
    instance: str
    source: str | None
    children: list["HierarchyNode"] = field(default_factory=list)
    recursive_reference: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "module": self.module,
            "instance": self.instance,
            "source": self.source,
            "recursive_reference": self.recursive_reference,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HierarchyNode":
        return cls(
            path=data["path"],
            module=data["module"],
            instance=data["instance"],
            source=data.get("source"),
            recursive_reference=bool(data.get("recursive_reference", False)),
            children=[cls.from_dict(item) for item in data.get("children", [])],
        )


@dataclass(slots=True)
class ReplacementTask:
    task_id: str
    instance_path: str
    module: str
    source: str | None
    kind: str
    dependencies: list[str] = field(default_factory=list)
    parent_path: str | None = None
    status: TaskStatus = TaskStatus.DISCOVERED
    recognition_rule: str | None = None
    verification_manifest: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReplacementTask":
        copy = dict(data)
        copy["status"] = TaskStatus(copy.get("status", TaskStatus.DISCOVERED))
        return cls(**copy)


@dataclass(slots=True)
class VerificationManifest:
    module: str
    top: str
    common_files: list[Path]
    fpga_files: list[Path]
    asic_files: list[Path]
    tests: list[str]
    seeds: list[int]
    comparison: ComparisonMode
    trace_file: str = "trace.jsonl"

    @property
    def all_files(self) -> list[Path]:
        return self.common_files + self.fpga_files + self.asic_files


@dataclass(slots=True)
class SimulationResult:
    backend: str
    test: str
    seed: int
    success: bool
    exit_code: int
    result_dir: Path
    trace_path: Path | None
    log_path: Path | None
    message: str = ""


@dataclass(slots=True)
class ComparisonResult:
    matched: bool
    mode: ComparisonMode
    checked_records: int
    differences: list[str] = field(default_factory=list)
