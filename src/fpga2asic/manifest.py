from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import HierarchyNode, ModuleDefinition


SCHEMA_VERSION = 1


class ManifestError(ValueError):
    pass


@dataclass(slots=True)
class DesignManifest:
    top: str
    source_files: list[Path]
    modules: dict[str, ModuleDefinition]
    hierarchy: HierarchyNode
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "top": self.top,
            "source_files": [str(path) for path in self.source_files],
            "modules": {name: module.to_dict() for name, module in sorted(self.modules.items())},
            "hierarchy": self.hierarchy.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignManifest":
        version = int(data.get("schema_version", 0))
        if version != SCHEMA_VERSION:
            raise ManifestError(f"Unsupported design manifest schema {version}; expected {SCHEMA_VERSION}")
        try:
            return cls(
                schema_version=version,
                top=data["top"],
                source_files=[Path(path) for path in data.get("source_files", [])],
                modules={
                    name: ModuleDefinition.from_dict(module)
                    for name, module in data.get("modules", {}).items()
                },
                hierarchy=HierarchyNode.from_dict(data["hierarchy"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError(f"Invalid design manifest: {exc}") from exc

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "DesignManifest":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError(f"Cannot read design manifest {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ManifestError("Design manifest root must be an object")
        return cls.from_dict(raw)
