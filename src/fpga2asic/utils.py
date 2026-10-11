from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath


def safe_component(value: str) -> str:
    """Return a stable filesystem component without allowing path traversal."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "item"
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:64]}-{digest}"


def safe_artifact_path(base: Path, artifact: str) -> Path:
    """Resolve a configured POSIX-style artifact path below base."""
    relative = PurePosixPath(artifact)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe artifact path: {artifact!r}")
    return base.joinpath(*relative.parts)

