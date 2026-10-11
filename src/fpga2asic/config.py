from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ComparisonMode, VerificationManifest


class ConfigError(ValueError):
    pass


_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ServerConfig:
    name: str
    type: str
    host: str | None = None
    user: str | None = None
    port: int = 22
    work_root: str = "/tmp/fpga2asic"
    ssh_executable: str = "ssh"
    scp_executable: str = "scp"
    ssh_options: tuple[str, ...] = ()

    @property
    def destination(self) -> str:
        if not self.host:
            raise ConfigError(f"SSH server {self.name!r} is missing host")
        return f"{self.user}@{self.host}" if self.user else self.host


@dataclass(frozen=True, slots=True)
class ToolConfig:
    name: str
    server: str
    command: str
    artifacts: tuple[str, ...] = ("trace.jsonl",)
    support_files: tuple[Path, ...] = ()
    environment: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    config_path: Path
    name: str
    root: Path
    top: str
    sources: tuple[str, ...]
    include_dirs: tuple[Path, ...]
    defines: tuple[str, ...]
    build_dir: Path
    design_manifest: Path
    verification_dir: Path
    ip_patterns: tuple[str, ...]
    servers: dict[str, ServerConfig]
    tools: dict[str, ToolConfig]

    def source_files(self) -> list[Path]:
        found: set[Path] = set()
        for pattern in self.sources:
            candidate = self.root / pattern
            if any(char in pattern for char in "*?["):
                matches = self.root.glob(pattern)
            elif candidate.is_dir():
                matches = candidate.rglob("*.v")
            else:
                matches = [candidate]
            for path in matches:
                if path.is_file() and path.suffix.lower() in {".v", ".sv", ".vh", ".svh"}:
                    found.add(path.resolve())
        return sorted(found)


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            if path.suffix.lower() == ".toml":
                return tomllib.load(stream)
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Cannot read configuration {path}: {exc}") from exc
    raise ConfigError("Configuration must be TOML or JSON")


def load_project_config(path: str | Path) -> ProjectConfig:
    config_path = Path(path).resolve()
    raw = _read_mapping(config_path)
    project = raw.get("project", {})
    config_dir = config_path.parent
    root = (config_dir / project.get("root", ".")).resolve()

    servers: dict[str, ServerConfig] = {}
    for name, item in raw.get("servers", {}).items():
        servers[name] = ServerConfig(
            name=name,
            type=item.get("type", "ssh"),
            host=item.get("host"),
            user=item.get("user"),
            port=int(item.get("port", 22)),
            work_root=item.get("work_root", "/tmp/fpga2asic"),
            ssh_executable=item.get("ssh_executable", "ssh"),
            scp_executable=item.get("scp_executable", "scp"),
            ssh_options=tuple(item.get("ssh_options", [])),
        )
    if "local" not in servers:
        servers["local"] = ServerConfig(name="local", type="local", work_root=str(root / ".remote"))

    tools: dict[str, ToolConfig] = {}
    for name, item in raw.get("tools", {}).items():
        server = item.get("server", "local")
        if server not in servers:
            raise ConfigError(f"Tool {name!r} refers to unknown server {server!r}")
        if not item.get("command"):
            raise ConfigError(f"Tool {name!r} is missing command")
        environment = {str(k): str(v) for k, v in item.get("environment", {}).items()}
        invalid_names = [key for key in environment if not _ENVIRONMENT_NAME.fullmatch(key)]
        if invalid_names:
            raise ConfigError(f"Tool {name!r} has invalid environment names: {invalid_names}")
        tools[name] = ToolConfig(
            name=name,
            server=server,
            command=item["command"],
            artifacts=tuple(item.get("artifacts", ["trace.jsonl"])),
            support_files=tuple((root / value).resolve() for value in item.get("support_files", [])),
            environment=environment,
            timeout_seconds=int(item.get("timeout_seconds", 3600)),
        )

    verification = raw.get("verification", {})
    default_patterns = (
        r"^RAMB\w*$",
        r"^DSP48\w*$",
        r"^xpm_\w+$",
        r"^(axi|axis)_\w+$",
        r"^blk_mem_gen\w*$",
        r"^fifo_generator\w*$",
    )
    return ProjectConfig(
        config_path=config_path,
        name=project.get("name", config_path.stem),
        root=root,
        top=project.get("top", ""),
        sources=tuple(project.get("sources", ["rtl/**/*.v", "rtl/**/*.sv"])),
        include_dirs=tuple((root / p).resolve() for p in project.get("include_dirs", [])),
        defines=tuple(project.get("defines", [])),
        build_dir=(root / project.get("build_dir", "build/fpga2asic")).resolve(),
        design_manifest=(
            root / project.get("design_manifest", "build/rtl-analysis/design-manifest.json")
        ).resolve(),
        verification_dir=(root / verification.get("manifests_dir", "verification/tasks")).resolve(),
        ip_patterns=tuple(project.get("ip_patterns", default_patterns)),
        servers=servers,
        tools=tools,
    )


def load_verification_manifest(path: Path, project_root: Path) -> VerificationManifest:
    raw = _read_mapping(path)

    def paths(name: str) -> list[Path]:
        return [(project_root / value).resolve() for value in raw.get(name, [])]

    try:
        return VerificationManifest(
            module=raw["module"],
            top=raw.get("top", "tb_top"),
            common_files=paths("common_files"),
            fpga_files=paths("fpga_files"),
            asic_files=paths("asic_files"),
            tests=list(raw.get("tests", ["default"])),
            seeds=[int(value) for value in raw.get("seeds", [1])],
            comparison=ComparisonMode(raw.get("comparison", "signal")),
            trace_file=raw.get("trace_file", "trace.jsonl"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid verification manifest {path}: {exc}") from exc
