from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .models import ComparisonMode, ComparisonResult


class TraceFormatError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TraceFormatError(f"{path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise TraceFormatError(f"{path}:{line_number}: each record must be an object")
        records.append(value)
    return records


def _limited_differences(items: Iterable[str], limit: int = 20) -> list[str]:
    result: list[str] = []
    for item in items:
        result.append(item)
        if len(result) >= limit:
            result.append("Difference list truncated")
            break
    return result


def compare_signal_records(
    golden: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> ComparisonResult:
    differences: list[str] = []
    if len(golden) != len(candidate):
        differences.append(f"Record count differs: golden={len(golden)}, candidate={len(candidate)}")
    for index, (left, right) in enumerate(zip(golden, candidate)):
        if left != right:
            differences.append(f"Record {index} differs: golden={left!r}, candidate={right!r}")
            if len(differences) >= 20:
                differences.append("Difference list truncated")
                break
    return ComparisonResult(
        matched=not differences,
        mode=ComparisonMode.SIGNAL,
        checked_records=min(len(golden), len(candidate)),
        differences=differences,
    )


_TIMING_FIELDS = {"cycle", "time", "timestamp", "ready_cycle", "response_cycle"}


def _normalize_transaction(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in _TIMING_FIELDS}


def _transaction_groups(records: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        normalized = _normalize_transaction(record)
        kind = str(normalized.get("event", normalized.get("kind", "unknown")))
        transaction_id = str(normalized.get("id", "__no_id__"))
        groups[(kind, transaction_id)].append(normalized)
    return groups


def compare_axi_transactions(
    golden: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> ComparisonResult:
    left_groups = _transaction_groups(golden)
    right_groups = _transaction_groups(candidate)
    differences: list[str] = []
    all_keys = sorted(set(left_groups) | set(right_groups))
    for key in all_keys:
        left = left_groups.get(key, [])
        right = right_groups.get(key, [])
        if left != right:
            differences.append(f"Transaction stream {key!r} differs: golden={left!r}, candidate={right!r}")
            if len(differences) >= 20:
                differences.append("Difference list truncated")
                break
    return ComparisonResult(
        matched=not differences,
        mode=ComparisonMode.AXI_TRANSACTION,
        checked_records=min(len(golden), len(candidate)),
        differences=differences,
    )


def compare_traces(golden_path: Path, candidate_path: Path, mode: ComparisonMode) -> ComparisonResult:
    golden = read_jsonl(golden_path)
    candidate = read_jsonl(candidate_path)
    if mode == ComparisonMode.SIGNAL:
        return compare_signal_records(golden, candidate)
    if mode == ComparisonMode.AXI_TRANSACTION:
        return compare_axi_transactions(golden, candidate)
    raise ValueError(f"Unsupported comparison mode: {mode}")

