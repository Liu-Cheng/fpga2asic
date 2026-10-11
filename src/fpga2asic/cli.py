from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_project_config
from .report import write_report
from .simulator import SimulationSetupError
from .trace import TraceFormatError
from .workflow import ProjectWorkspace, WorkflowError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fpga2asic")
    parser.add_argument("-c", "--config", default="project.toml", help="Project TOML/JSON file")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan", help="Create replacement tasks from design-manifest.json")
    subparsers.add_parser("list", help="List replacement tasks")
    subparsers.add_parser("check-tb", help="Check reusable testbench manifests")
    baseline = subparsers.add_parser("baseline", help="Run Xilinx baseline simulation")
    baseline.add_argument("task_id")
    replace = subparsers.add_parser("replace", help="Run ASIC simulation and compare traces")
    replace.add_argument("task_id")
    subparsers.add_parser("run", help="Run all currently ready tasks bottom-up")
    subparsers.add_parser("report", help="Generate the project report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project = load_project_config(args.config)
        workspace = ProjectWorkspace(project)
        if args.command == "plan":
            tasks = workspace.plan()
            print(f"Created {len(tasks)} replacement tasks from {project.design_manifest}")
            print(workspace.analysis_dir)
        elif args.command == "list":
            for task in workspace.load_tasks():
                print(f"{task.task_id}\t{task.status.value}\t{task.kind}\t{task.instance_path}")
        elif args.command == "check-tb":
            failed = 0
            for task in workspace.load_tasks():
                ready, problems = workspace.check_testbench(task)
                print(f"{task.task_id}\t{'READY' if ready else 'BLOCKED'}\t{task.instance_path}")
                for problem in problems:
                    print(f"  - {problem}")
                failed += int(not ready)
            return 1 if failed else 0
        elif args.command == "baseline":
            task = workspace.run_baseline(args.task_id)
            print(f"{task.task_id}: {task.status.value}")
            return 0 if task.status.value == "fpga_baseline_pass" else 1
        elif args.command == "replace":
            summary = workspace.run_replacement(args.task_id)
            print(f"{summary.task.task_id}: {summary.task.status.value}")
            return 0 if summary.task.status.value == "accepted" else 1
        elif args.command == "run":
            summaries = workspace.run_ready_tasks()
            tasks = workspace.load_tasks()
            report = write_report(project, tasks)
            print(f"Processed {len(summaries)} task runs; report: {report}")
            return 0 if all(task.status.value == "accepted" for task in tasks) else 2
        elif args.command == "report":
            report = write_report(project, workspace.load_tasks())
            print(report)
        return 0
    except (ConfigError, WorkflowError, SimulationSetupError, TraceFormatError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
