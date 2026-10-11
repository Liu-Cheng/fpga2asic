from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import ConfigError, ProjectConfig, load_verification_manifest
from .manifest import DesignManifest, ManifestError
from .models import ComparisonResult, ReplacementTask, TaskStatus, VerificationManifest
from .planner import build_replacement_tasks
from .simulator import SimulationRequest, SimulationSetupError, make_simulator
from .trace import TraceFormatError, compare_traces
from .utils import safe_artifact_path, safe_component


class WorkflowError(RuntimeError):
    pass


@dataclass(slots=True)
class TaskRunSummary:
    task: ReplacementTask
    comparisons: list[ComparisonResult]


class ProjectWorkspace:
    def __init__(self, project: ProjectConfig):
        self.project = project

    @property
    def analysis_dir(self) -> Path:
        return self.project.build_dir / "analysis"

    @property
    def task_dir(self) -> Path:
        return self.project.build_dir / "tasks"

    def task_path(self, task_id: str) -> Path:
        return self.task_dir / f"{task_id}.json"

    def save_task(self, task: ReplacementTask) -> None:
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self.task_path(task.task_id).write_text(
            json.dumps(task.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_task(self, task_id: str) -> ReplacementTask:
        path = self.task_path(task_id)
        if not path.is_file():
            raise WorkflowError(f"Unknown task {task_id!r}; run ipverify plan first")
        return ReplacementTask.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def load_tasks(self) -> list[ReplacementTask]:
        if not self.task_dir.is_dir():
            raise WorkflowError("No task plan exists; run ipverify plan first")
        return [
            ReplacementTask.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self.task_dir.glob("task_*.json"))
        ]

    def plan(self) -> list[ReplacementTask]:
        """Create conversion tasks from an external design manifest; never parse RTL here."""
        if not self.project.design_manifest.is_file():
            raise WorkflowError(
                f"Design manifest is missing: {self.project.design_manifest}; "
                "run rtl-manifest or configure the output of the existing extraction tool"
            )
        try:
            design = DesignManifest.load(self.project.design_manifest)
        except ManifestError as exc:
            raise WorkflowError(str(exc)) from exc
        if self.project.top and self.project.top != design.top:
            raise WorkflowError(
                f"Configured top {self.project.top!r} does not match design manifest top {design.top!r}"
            )
        tasks = build_replacement_tasks(design.hierarchy, self.project.ip_patterns)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        old = {task.task_id: task for task in self.load_tasks()} if self.task_dir.is_dir() else {}
        for task in tasks:
            previous = old.get(task.task_id)
            if previous and previous.instance_path == task.instance_path and previous.module == task.module:
                task.status = previous.status
                task.verification_manifest = previous.verification_manifest
                task.notes = previous.notes
            manifest = self.find_manifest(task)
            if manifest:
                task.verification_manifest = str(manifest)
            self.save_task(task)
            self._write_manifest_skeleton(task)

        (self.analysis_dir / "tasks.json").write_text(
            json.dumps([task.to_dict() for task in tasks], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return tasks

    def find_manifest(self, task: ReplacementTask) -> Path | None:
        candidates = [
            self.project.verification_dir / f"{task.task_id}.toml",
            self.project.verification_dir / f"{task.task_id}.json",
            self.project.verification_dir / f"{task.module}.toml",
            self.project.verification_dir / f"{task.module}.json",
        ]
        return next((path for path in candidates if path.is_file()), None)

    def _write_manifest_skeleton(self, task: ReplacementTask) -> None:
        self.project.verification_dir.mkdir(parents=True, exist_ok=True)
        path = self.project.verification_dir / f"{task.task_id}.toml.example"
        if path.exists() or self.find_manifest(task):
            return
        comparison = "axi_transaction" if task.kind == "axi" else "signal"
        path.write_text(
            f'''# Copy this file to {task.task_id}.toml and fill in the file lists.\n'''
            f'''module = "{task.module}"\n'''
            '''top = "tb_top"\n'''
            f'''comparison = "{comparison}"\n'''
            '''trace_file = "trace.jsonl"\n'''
            '''tests = ["default"]\n'''
            '''seeds = [1]\n'''
            '''common_files = ["verification/common/tb_top.sv"]\n'''
            f'''fpga_files = ["{task.source or 'path/to/original.v'}"]\n'''
            f'''asic_files = ["replacements/{task.module}.v"]\n''',
            encoding="utf-8",
        )

    def manifest_for(self, task: ReplacementTask) -> VerificationManifest:
        manifest_path = self.find_manifest(task)
        if not manifest_path:
            raise WorkflowError(f"Task {task.task_id} has no verification manifest")
        manifest = load_verification_manifest(manifest_path, self.project.root)
        if manifest.module != task.module:
            raise WorkflowError(
                f"Verification manifest {manifest_path} targets {manifest.module!r}, expected {task.module!r}"
            )
        return manifest

    def check_testbench(self, task: ReplacementTask, save: bool = True) -> tuple[bool, list[str]]:
        problems: list[str] = []
        manifest_path = self.find_manifest(task)
        if not manifest_path:
            problems.append("verification manifest is missing")
        else:
            try:
                manifest = load_verification_manifest(manifest_path, self.project.root)
                if not manifest.common_files:
                    problems.append("common_files is empty")
                if not manifest.fpga_files:
                    problems.append("fpga_files is empty")
                if not manifest.asic_files:
                    problems.append("asic_files is empty")
                if not manifest.tests:
                    problems.append("tests is empty")
                for path in manifest.all_files:
                    if not path.is_file():
                        problems.append(f"file does not exist: {path}")
            except ConfigError as exc:
                problems.append(str(exc))
        if save:
            if problems:
                task.status = TaskStatus.BLOCKED_NO_TB
            elif task.status in {TaskStatus.DISCOVERED, TaskStatus.BLOCKED_NO_TB}:
                task.status = TaskStatus.TB_READY
            task.notes = [note for note in task.notes if not note.startswith("TB: ")]
            task.notes.extend(f"TB: {problem}" for problem in problems)
            task.verification_manifest = str(manifest_path) if manifest_path else None
            self.save_task(task)
        return not problems, problems

    def _case_result_dir(self, task: ReplacementTask, backend: str, test: str, seed: int) -> Path:
        return self.project.build_dir / "results" / task.task_id / backend / safe_component(test) / str(seed)

    def run_baseline(self, task_id: str) -> ReplacementTask:
        task = self.load_task(task_id)
        ready, problems = self.check_testbench(task)
        if not ready:
            raise WorkflowError(f"Testbench is not ready: {'; '.join(problems)}")
        manifest = self.manifest_for(task)
        simulator = make_simulator(self.project, "fpga")
        task.status = TaskStatus.FPGA_BASELINE_RUNNING
        self.save_task(task)
        for test in manifest.tests:
            for seed in manifest.seeds:
                result = simulator.run(SimulationRequest(task.task_id, "fpga", manifest, test, seed))
                if not result.success:
                    task.status = TaskStatus.FPGA_BASELINE_FAIL
                    task.notes.append(f"FPGA {test}/{seed}: {result.message or 'simulation failed'}")
                    self.save_task(task)
                    return task
        task.status = TaskStatus.FPGA_BASELINE_PASS
        self.save_task(task)
        return task

    def run_replacement(self, task_id: str, ensure_baseline: bool = True) -> TaskRunSummary:
        task = self.load_task(task_id)
        tasks_by_id = {item.task_id: item for item in self.load_tasks()}
        blocked_dependencies = [
            dependency
            for dependency in task.dependencies
            if tasks_by_id.get(dependency) is None
            or tasks_by_id[dependency].status != TaskStatus.ACCEPTED
        ]
        if blocked_dependencies:
            raise WorkflowError("Dependencies are not accepted: " + ", ".join(blocked_dependencies))
        ready, problems = self.check_testbench(task)
        if not ready:
            raise WorkflowError(f"Testbench is not ready: {'; '.join(problems)}")
        if ensure_baseline and task.status not in {
            TaskStatus.FPGA_BASELINE_PASS,
            TaskStatus.ASIC_SIM_FAIL,
            TaskStatus.COMPARE_FAIL,
            TaskStatus.COMPARE_PASS,
            TaskStatus.ACCEPTED,
        }:
            task = self.run_baseline(task_id)
        if task.status == TaskStatus.FPGA_BASELINE_FAIL:
            return TaskRunSummary(task=task, comparisons=[])

        manifest = self.manifest_for(task)
        simulator = make_simulator(self.project, "asic")
        task.status = TaskStatus.ASIC_SIM_RUNNING
        self.save_task(task)
        comparisons: list[ComparisonResult] = []
        for test in manifest.tests:
            for seed in manifest.seeds:
                result = simulator.run(SimulationRequest(task.task_id, "asic", manifest, test, seed))
                if not result.success or not result.trace_path:
                    task.status = TaskStatus.ASIC_SIM_FAIL
                    task.notes.append(f"ASIC {test}/{seed}: {result.message or 'simulation failed'}")
                    self.save_task(task)
                    return TaskRunSummary(task=task, comparisons=comparisons)
                golden = safe_artifact_path(
                    self._case_result_dir(task, "fpga", test, seed), manifest.trace_file
                )
                if not golden.is_file():
                    raise WorkflowError(f"Golden trace is missing: {golden}; rerun baseline")
                comparison = compare_traces(golden, result.trace_path, manifest.comparison)
                comparisons.append(comparison)
                comparison_path = result.result_dir / "comparison.json"
                comparison_path.write_text(
                    json.dumps(
                        {
                            "matched": comparison.matched,
                            "mode": comparison.mode.value,
                            "checked_records": comparison.checked_records,
                            "differences": comparison.differences,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                if not comparison.matched:
                    task.status = TaskStatus.COMPARE_FAIL
                    task.notes.extend(f"COMPARE {test}/{seed}: {item}" for item in comparison.differences[:5])
                    self.save_task(task)
                    return TaskRunSummary(task=task, comparisons=comparisons)

        task.status = TaskStatus.ACCEPTED
        self.save_task(task)
        return TaskRunSummary(task=task, comparisons=comparisons)

    def run_ready_tasks(self) -> list[TaskRunSummary]:
        summaries: list[TaskRunSummary] = []
        while True:
            tasks = self.load_tasks()
            by_id = {task.task_id: task for task in tasks}
            candidates = [
                task
                for task in tasks
                if task.status in {
                    TaskStatus.DISCOVERED,
                    TaskStatus.BLOCKED_NO_TB,
                    TaskStatus.TB_READY,
                    TaskStatus.FPGA_BASELINE_PASS,
                }
                and all(by_id[dep].status == TaskStatus.ACCEPTED for dep in task.dependencies)
            ]
            if not candidates:
                break
            progress = False
            for task in sorted(candidates, key=lambda item: (-item.instance_path.count("/"), item.instance_path)):
                ready, _ = self.check_testbench(task)
                if not ready:
                    continue
                before = task.status
                try:
                    summary = self.run_replacement(task.task_id)
                except (WorkflowError, SimulationSetupError, TraceFormatError) as exc:
                    task = self.load_task(task.task_id)
                    task.notes.append(f"RUN: {exc}")
                    self.save_task(task)
                    continue
                summaries.append(summary)
                if summary.task.status == TaskStatus.ACCEPTED or summary.task.status != before:
                    progress = True
            if not progress:
                break
        return summaries
