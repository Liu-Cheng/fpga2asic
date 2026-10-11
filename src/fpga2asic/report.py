from __future__ import annotations

from collections import Counter
from pathlib import Path

from .config import ProjectConfig
from .models import ReplacementTask, TaskStatus
from .manifest import DesignManifest, ManifestError


def render_report(project: ProjectConfig, tasks: list[ReplacementTask]) -> str:
    counts = Counter(task.status.value for task in tasks)
    accepted = sum(1 for task in tasks if task.status == TaskStatus.ACCEPTED)
    manifest_top = ""
    if project.design_manifest.is_file():
        try:
            manifest_top = DesignManifest.load(project.design_manifest).top
        except ManifestError:
            pass
    lines = [
        f"# {project.name} FPGA IP replacement report",
        "",
        "## Summary",
        "",
        f"- Top module: `{project.top or manifest_top or 'unknown'}`",
        f"- Replacement tasks: {len(tasks)}",
        f"- Accepted: {accepted}",
        f"- Completion: {accepted / len(tasks):.1%}" if tasks else "- Completion: 100.0%",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Tasks",
            "",
            "| Task | Instance | Kind | Dependencies | Status |",
            "|---|---|---|---|---|",
        ]
    )
    for task in sorted(tasks, key=lambda item: item.instance_path):
        dependencies = ", ".join(task.dependencies) or "-"
        lines.append(
            f"| `{task.task_id}` | `{task.instance_path}` | `{task.kind}` | {dependencies} | `{task.status.value}` |"
        )
        if task.notes:
            for note in task.notes:
                lines.append(f"<!-- {task.task_id}: {note.replace('--', '—')} -->")
    manual = [task for task in tasks if task.status != TaskStatus.ACCEPTED]
    lines.extend(["", "## Open items", ""])
    if not manual:
        lines.append("All replacement tasks have passed verification.")
    else:
        for task in manual:
            lines.append(f"### {task.task_id} — `{task.instance_path}`")
            lines.append("")
            lines.append(f"Current status: `{task.status.value}`")
            lines.append("")
            if task.notes:
                lines.extend(f"- {note}" for note in task.notes)
            else:
                lines.append("- Not executed yet.")
            lines.append("")
    return "\n".join(lines) + "\n"


def write_report(project: ProjectConfig, tasks: list[ReplacementTask]) -> Path:
    path = project.build_dir / "reports" / "summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(project, tasks), encoding="utf-8")
    return path
