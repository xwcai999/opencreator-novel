#!/usr/bin/env python3
"""Parse and audit the versioned expectation ledger."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from studio_common import is_kebab_id, parse_document


STATUSES = {"planned", "planted", "reinforced", "partial", "active", "fulfilled", "dropped"}
TERMINAL_STATUSES = {"fulfilled", "dropped"}
EXPECTED_COLUMNS = (
    "ID", "类型", "承诺", "状态", "首次出现", "最近推进", "兑现窗口", "正文证据", "禁止提前揭露", "所属驱动"
)
LONG_LINE_TYPES = ("长钩", "伏笔", "悬疑", "秘密", "真相", "线索")
CHAPTER_RE = re.compile(r"第\s*0*(\d+)\s*章")
RANGE_RE = re.compile(r"第\s*0*(\d+)\s*[—–~-]\s*0*(\d+)\s*章")


@dataclass(frozen=True)
class LedgerItem:
    item_id: str
    kind: str
    promise: str
    status: str
    first_seen: str
    last_touched: str
    payoff_window: str
    evidence: str
    reveal_guard: str
    driver: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.item_id,
            "kind": self.kind,
            "promise": self.promise,
            "status": self.status,
            "first_seen": self.first_seen,
            "last_touched": self.last_touched,
            "payoff_window": self.payoff_window,
            "evidence": self.evidence,
            "reveal_guard": self.reveal_guard,
            "driver": self.driver,
        }


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _chapter_numbers(value: str) -> list[int]:
    numbers = [int(item) for item in CHAPTER_RE.findall(value)]
    for start, end in RANGE_RE.findall(value):
        numbers.extend((int(start), int(end)))
    return numbers


def _window_end(value: str) -> int | None:
    ranges = RANGE_RE.findall(value)
    if ranges:
        return max(int(end) for _, end in ranges)
    numbers = _chapter_numbers(value)
    return max(numbers) if numbers else None


def parse_ledger(path: Path) -> tuple[dict[str, object], list[LedgerItem], list[str]]:
    meta, body = parse_document(path)
    errors: list[str] = []
    version = int(meta.get("ledger-version") or 0)
    if version != 2:
        return meta, [], errors

    lines = body.splitlines()
    header_index = next((index for index, line in enumerate(lines) if line.strip().startswith("| ID |")), -1)
    if header_index < 0 or header_index + 1 >= len(lines):
        return meta, [], ["状态/待兑现.md: ledger-version=2 但缺少标准台账表头"]
    header = tuple(_cells(lines[header_index]))
    if header != EXPECTED_COLUMNS:
        errors.append("状态/待兑现.md: 台账列必须严格为 " + " | ".join(EXPECTED_COLUMNS))

    items: list[LedgerItem] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines[header_index + 2 :], start=header_index + 3):
        if not line.strip().startswith("|"):
            if items and line.strip():
                break
            continue
        cells = _cells(line)
        if len(cells) == 1 and not cells[0]:
            continue
        if len(cells) != len(EXPECTED_COLUMNS):
            errors.append(f"状态/待兑现.md:{line_number}: 台账列数应为 {len(EXPECTED_COLUMNS)}")
            continue
        item = LedgerItem(*cells)
        if not is_kebab_id(item.item_id):
            errors.append(f"状态/待兑现.md:{line_number}: 非法 ID {item.item_id!r}")
        elif item.item_id in seen:
            errors.append(f"状态/待兑现.md:{line_number}: 重复 ID {item.item_id}")
        seen.add(item.item_id)
        if item.status not in STATUSES:
            errors.append(f"状态/待兑现.md:{line_number}: 非法状态 {item.status!r}")
        for label, value in zip(EXPECTED_COLUMNS[1:], cells[1:]):
            if not value:
                errors.append(f"状态/待兑现.md:{line_number}: {label} 不能为空")
        if item.status == "planned":
            if item.first_seen != "未出现" or item.last_touched != "未出现":
                errors.append(f"状态/待兑现.md:{line_number}: planned 项的首次出现和最近推进必须为“未出现”")
        elif item.status not in TERMINAL_STATUSES or item.status == "fulfilled":
            if not _chapter_numbers(item.first_seen) or not _chapter_numbers(item.last_touched):
                errors.append(f"状态/待兑现.md:{line_number}: {item.status} 项必须提供首次出现和最近推进章节")
        if item.status == "fulfilled" and any(marker in item.kind for marker in LONG_LINE_TYPES):
            if "最终兑现" not in item.evidence and "完整揭示" not in item.evidence:
                errors.append(
                    f"状态/待兑现.md:{line_number}: 长线项 {item.item_id} 标为 fulfilled 时，正文证据必须明确“最终兑现”或“完整揭示”"
                )
        items.append(item)
    return meta, items, errors


def audit_ledger(path: Path, target_chapter: int = 0) -> dict[str, object]:
    meta, items, errors = parse_ledger(path)
    version = int(meta.get("ledger-version") or 0)
    warnings: list[str] = []
    active: list[LedgerItem] = []
    overdue: list[str] = []
    cold: list[str] = []
    cold_after = int(meta.get("cold-after-chapters") or 8)

    if version != 2:
        warnings.append("状态/待兑现.md: 旧版自由文本台账；建议迁移到 ledger-version=2")
    else:
        for item in items:
            if item.status in TERMINAL_STATUSES:
                continue
            active.append(item)
            end = _window_end(item.payoff_window)
            if target_chapter > 0 and end is not None and target_chapter > end:
                overdue.append(item.item_id)
                errors.append(
                    f"状态/待兑现.md: {item.item_id} 已超过兑现窗口 {item.payoff_window}；续写前必须兑现、废弃或重排窗口"
                )
            touched = _chapter_numbers(item.last_touched)
            if target_chapter > 0 and touched and target_chapter - max(touched) > cold_after:
                cold.append(item.item_id)
                warnings.append(
                    f"状态/待兑现.md: 冷线 {item.item_id} 已超过 {cold_after} 章未推进；本轮规划必须明确强化、兑现或继续冷藏理由"
                )

    return {
        "ok": not errors,
        "ledger_version": version,
        "tracking_start_chapter": int(meta.get("tracking-start-chapter") or 0),
        "target_chapter": target_chapter,
        "items": [item.as_dict() for item in items],
        "active_items": [item.as_dict() for item in active],
        "overdue": overdue,
        "cold": cold,
        "errors": errors,
        "warnings": warnings,
    }


def render_active_items(items: list[dict[str, str]]) -> str:
    lines = [
        "## 强制连续性：非终态待兑现项",
        "",
        "以下内容优先于词项检索结果；不得因只读取上一章而省略。",
        "",
        "| ID | 类型 | 承诺 | 状态 | 首次出现 | 最近推进 | 兑现窗口 | 正文证据 | 禁止提前揭露 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            "| {id} | {kind} | {promise} | {status} | {first_seen} | {last_touched} | "
            "{payoff_window} | {evidence} | {reveal_guard} |".format(**item)
        )
    if not items:
        lines.append("| none | 无 | 当前没有非终态待兑现项 | active | 未出现 | 未出现 | 持续 | 台账为空 | 无 |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="审计 Novel Studio 待兑现台账")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--target-chapter", type=int, default=0)
    args = parser.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    try:
        result = audit_ledger(root / "状态" / "待兑现.md", args.target_chapter)
    except (OSError, ValueError) as exc:
        result = {"ok": False, "errors": [str(exc)], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
