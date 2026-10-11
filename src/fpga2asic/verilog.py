from __future__ import annotations

import re
from pathlib import Path

from .models import HierarchyNode, Instance, ModuleDefinition


_MODULE_RE = re.compile(
    r"\bmodule\s+(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\b(?P<body>.*?)\bendmodule\b",
    re.DOTALL,
)
_INSTANCE_RE = re.compile(
    r"(?m)^\s*(?P<module>[A-Za-z_][A-Za-z0-9_$]*)\s*"
    r"(?:#\s*\((?P<parameters>.*?)\)\s*)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_$]*)\s*"
    r"\((?P<ports>.*?)\)\s*;",
    re.DOTALL,
)
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_NON_INSTANCE_WORDS = {
    "module", "function", "task", "always", "initial", "assign", "if", "else",
    "for", "while", "case", "casex", "casez", "generate", "begin", "end",
    "wire", "reg", "input", "output", "inout", "parameter", "localparam",
}


class VerilogParseError(ValueError):
    pass


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def parse_verilog_files(paths: list[Path]) -> dict[str, ModuleDefinition]:
    modules: dict[str, ModuleDefinition] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        clean = _COMMENT_RE.sub(lambda match: "\n" * match.group(0).count("\n"), text)
        for module_match in _MODULE_RE.finditer(clean):
            name = module_match.group("name")
            body = module_match.group("body")
            body_offset = module_match.start("body")
            instances: list[Instance] = []
            for instance_match in _INSTANCE_RE.finditer(body):
                child_module = instance_match.group("module")
                if child_module.lower() in _NON_INSTANCE_WORDS:
                    continue
                instances.append(
                    Instance(
                        module=child_module,
                        name=instance_match.group("name"),
                        parameters=(instance_match.group("parameters") or "").strip(),
                        ports=(instance_match.group("ports") or "").strip(),
                        source_line=_line_number(clean, body_offset + instance_match.start()),
                    )
                )
            modules[name] = ModuleDefinition(
                name=name,
                source=path,
                start_line=_line_number(clean, module_match.start()),
                instances=instances,
            )
    return modules


def build_hierarchy(modules: dict[str, ModuleDefinition], top: str) -> HierarchyNode:
    if top not in modules:
        raise VerilogParseError(f"Top module {top!r} was not found")

    def visit(module_name: str, instance_name: str, path: str, stack: tuple[str, ...]) -> HierarchyNode:
        definition = modules.get(module_name)
        node = HierarchyNode(
            path=path,
            module=module_name,
            instance=instance_name,
            source=str(definition.source) if definition else None,
        )
        if module_name in stack:
            node.recursive_reference = True
            return node
        if definition:
            for child in definition.instances:
                child_path = f"{path}/{child.name}"
                node.children.append(visit(child.module, child.name, child_path, stack + (module_name,)))
        return node

    return visit(top, top, top, ())


