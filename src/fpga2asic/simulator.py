from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig, ToolConfig
from .executor import ExecutionJob, make_runner
from .models import SimulationResult, VerificationManifest
from .utils import safe_artifact_path, safe_component


class SimulationSetupError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SimulationRequest:
    task_id: str
    backend: str
    manifest: VerificationManifest
    test: str
    seed: int


class SimulatorBackend:
    def __init__(self, project: ProjectConfig, tool: ToolConfig):
        self.project = project
        self.tool = tool
        self.server = project.servers[tool.server]

    def run(self, request: SimulationRequest) -> SimulationResult:
        stage_dir = (
            self.project.build_dir
            / "work"
            / request.task_id
            / request.backend
            / safe_component(request.test)
            / str(request.seed)
            / uuid.uuid4().hex[:12]
        )
        result_dir = (
            self.project.build_dir
            / "results"
            / request.task_id
            / request.backend
            / safe_component(request.test)
            / str(request.seed)
        )
        stage_dir.mkdir(parents=True)
        result_dir.mkdir(parents=True, exist_ok=True)

        files = list(request.manifest.common_files)
        if request.backend == "fpga":
            files.extend(request.manifest.fpga_files)
        elif request.backend == "asic":
            files.extend(request.manifest.asic_files)
        else:
            raise SimulationSetupError(f"Unknown simulation backend {request.backend!r}")
        missing = [str(path) for path in files if not path.is_file()]
        if missing:
            raise SimulationSetupError("Missing simulation files: " + ", ".join(missing))

        staged_files: list[str] = []
        seen_sources: set[Path] = set()
        for index, source in enumerate(files):
            source = source.resolve()
            if source in seen_sources:
                continue
            seen_sources.add(source)
            try:
                relative = source.relative_to(self.project.root)
                destination = stage_dir / "src" / "project" / relative
            except ValueError:
                destination = stage_dir / "src" / "external" / f"{index:04d}" / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            staged_files.append(destination.relative_to(stage_dir).as_posix())

        staged_include_dirs: list[str] = []
        for index, include_dir in enumerate(self.project.include_dirs):
            if not include_dir.is_dir():
                raise SimulationSetupError(f"Missing include directory: {include_dir}")
            try:
                relative = include_dir.relative_to(self.project.root)
                destination = stage_dir / "src" / "project" / relative
            except ValueError:
                destination = stage_dir / "src" / "include" / f"{index:04d}"
            shutil.copytree(include_dir, destination, dirs_exist_ok=True)
            staged_include_dirs.append(destination.relative_to(stage_dir).as_posix())

        for index, source in enumerate(self.tool.support_files):
            if not source.is_file():
                raise SimulationSetupError(f"Missing tool support file: {source}")
            destination = stage_dir / "tool" / f"{index:04d}_{source.name}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        (stage_dir / "filelist.f").write_text("\n".join(staged_files) + "\n", encoding="utf-8")
        (stage_dir / "include_dirs.txt").write_text(
            "\n".join(staged_include_dirs) + ("\n" if staged_include_dirs else ""), encoding="utf-8"
        )
        manifest_data = {
            "task_id": request.task_id,
            "backend": request.backend,
            "top": request.manifest.top,
            "test": request.test,
            "seed": request.seed,
            "trace_file": request.manifest.trace_file,
            "files": staged_files,
            "include_dirs": staged_include_dirs,
        }
        (stage_dir / "simulation.json").write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        values = {
            "top": request.manifest.top,
            "test": request.test,
            "seed": str(request.seed),
            "trace": request.manifest.trace_file,
            "filelist": "filelist.f",
            "include_dirs": "include_dirs.txt",
            "manifest": "simulation.json",
            "task_id": request.task_id,
            "backend": request.backend,
        }
        try:
            command = self.tool.command.format_map(values)
        except KeyError as exc:
            raise SimulationSetupError(f"Unknown placeholder in tool command: {exc}") from exc

        artifacts = tuple(dict.fromkeys((*self.tool.artifacts, request.manifest.trace_file)))
        # Prevent a successful command that forgot to emit a trace from reusing an older result.
        for artifact in artifacts:
            prior = safe_artifact_path(result_dir, artifact)
            if prior.is_file():
                prior.unlink()
        execution = make_runner(self.server).run(
            ExecutionJob(
                name=f"{request.task_id}-{request.backend}-{request.test}-{request.seed}",
                workspace=stage_dir,
                result_dir=result_dir,
                command=command,
                artifacts=artifacts,
                environment=self.tool.environment,
                timeout_seconds=self.tool.timeout_seconds,
            )
        )
        trace_path = safe_artifact_path(result_dir, request.manifest.trace_file)
        log_path = result_dir / "runner.stdout.log"
        return SimulationResult(
            backend=request.backend,
            test=request.test,
            seed=request.seed,
            success=execution.success and trace_path.is_file(),
            exit_code=execution.exit_code,
            result_dir=result_dir,
            trace_path=trace_path if trace_path.is_file() else None,
            log_path=log_path if log_path.is_file() else None,
            message=execution.message,
        )


def make_simulator(project: ProjectConfig, backend: str) -> SimulatorBackend:
    tool_name = "xilinx" if backend == "fpga" else "vcs"
    if tool_name not in project.tools:
        raise SimulationSetupError(f"Tool [{tool_name}] is not configured")
    return SimulatorBackend(project, project.tools[tool_name])
