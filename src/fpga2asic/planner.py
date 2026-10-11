from __future__ import annotations

import hashlib
import re

from .models import HierarchyNode, ReplacementTask


def _task_id(instance_path: str) -> str:
    digest = hashlib.sha1(instance_path.encode("utf-8")).hexdigest()[:10]
    return f"task_{digest}"


def classify_ip(module: str, patterns: tuple[str, ...]) -> tuple[str, str] | None:
    for pattern in patterns:
        if re.search(pattern, module, re.IGNORECASE):
            lowered = module.lower()
            if "axi" in lowered or "axis" in lowered:
                kind = "axi"
            elif "ram" in lowered or "mem" in lowered:
                kind = "memory"
            elif "fifo" in lowered:
                kind = "fifo"
            elif "dsp" in lowered or "mult" in lowered or "mac" in lowered:
                kind = "dsp"
            else:
                kind = "digital_ip"
            return kind, pattern
    return None


def build_replacement_tasks(hierarchy: HierarchyNode, patterns: tuple[str, ...]) -> list[ReplacementTask]:
    """Select replacement nodes from an already-extracted design hierarchy."""
    tasks: dict[str, ReplacementTask] = {}

    def collect(node: HierarchyNode, parent: str | None) -> list[str]:
        descendant_task_ids: list[str] = []
        for child in node.children:
            descendant_task_ids.extend(collect(child, node.path))
        classification = classify_ip(node.module, patterns)
        if classification:
            task_id = _task_id(node.path)
            nearest: list[str] = []
            candidates = sorted(
                descendant_task_ids,
                key=lambda item: tasks[item].instance_path.count("/"),
            )
            for candidate_id in candidates:
                candidate_path = tasks[candidate_id].instance_path
                if not any(candidate_path.startswith(tasks[item].instance_path + "/") for item in nearest):
                    nearest.append(candidate_id)
            kind, rule = classification
            tasks[task_id] = ReplacementTask(
                task_id=task_id,
                instance_path=node.path,
                module=node.module,
                source=node.source,
                kind=kind,
                dependencies=nearest,
                parent_path=parent,
                recognition_rule=rule,
            )
            return [task_id]
        return descendant_task_ids

    collect(hierarchy, None)
    return sorted(tasks.values(), key=lambda task: (-task.instance_path.count("/"), task.instance_path))

