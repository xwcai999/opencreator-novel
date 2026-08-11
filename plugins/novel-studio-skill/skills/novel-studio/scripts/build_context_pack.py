#!/usr/bin/env python3
"""Build a bounded, derived context pack for the next chapter task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from expectation_ledger import audit_ledger, render_active_items
from retrieve_context import retrieve
from studio_common import as_list, atomic_write_text, chapter_number, ensure_within, parse_document
from validate_project import validate_project


def _find_numbered_file(directory: Path, number: int) -> Path | None:
    if not directory.is_dir() or number <= 0:
        return None
    matches: list[Path] = []
    for path in directory.rglob("*.md"):
        try:
            metadata, _ = parse_document(path)
        except ValueError:
            metadata = {}
        if chapter_number(path, metadata) == number:
            matches.append(path)
    return sorted(matches, key=lambda item: item.as_posix())[0] if matches else None


def _active_style_profile(root: Path) -> Path | None:
    path = root / "设定" / "文风档案.md"
    if not path.is_file():
        return None
    metadata, _ = parse_document(path)
    if metadata.get("type") == "style-profile" and metadata.get("status") == "active":
        return path
    return None


def build_context(root: Path, chapter: int, query: str, max_chars: int) -> tuple[str, list[str]]:
    root = root.expanduser().resolve()
    validation = validate_project(root)
    if not validation["ok"]:
        raise ValueError("项目硬门禁未通过: " + "；".join(validation["errors"]))

    ledger_path = root / "状态" / "待兑现.md"
    ledger_audit = audit_ledger(ledger_path, chapter)
    if not ledger_audit["ok"]:
        raise ValueError("待兑现台账门禁未通过: " + "；".join(ledger_audit["errors"]))
    mandatory_ledger = render_active_items(ledger_audit["active_items"])
    if len(mandatory_ledger) > max_chars - 1_500:
        raise ValueError("非终态待兑现项超过上下文预算；请提高 --max-chars，禁止截断连续性硬约束")

    selected: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    seen.add(ledger_path.resolve())

    def add(path: Path | None, reason: str) -> None:
        if path and path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                selected.append((resolved, reason))
                seen.add(resolved)

    add(root / "作品.md", "作品契约")
    add(root / "状态" / "当前状态.md", "当前权威状态")
    add(root / "设定" / "读者契约.md", "读者契约")
    add(_active_style_profile(root), "用户确认的 active 文风档案")
    add(root / "大纲" / "总纲.md", "全书方向")
    target_outline = _find_numbered_file(root / "大纲" / "细纲", chapter)
    add(target_outline, "目标章节细纲")
    if target_outline:
        outline_meta, _ = parse_document(target_outline)
        for relative in as_list(outline_meta.get("continuity-sources")):
            if relative:
                add(root / str(relative), "章纲显式连续性来源")
    add(_find_numbered_file(root / "正文", chapter - 1), "上一章正文")

    retrieval = retrieve(root, query, top_k=8) if query.strip() else {"results": []}
    for item in retrieval["results"]:
        add(root / str(item["path"]), f"词项检索 score={item['score']}")

    header = [
        "# 最小上下文包",
        "",
        f"- 目标章节：{chapter if chapter > 0 else '未指定'}",
        f"- 写作任务：{query or '未指定'}",
        f"- 字符预算：{max_chars}",
        "- 性质：派生物；不得作为权威状态回写",
        "",
    ]
    output_parts = ["\n".join(header), mandatory_ledger]
    used = sum(len(part) for part in output_parts)
    included: list[str] = ["状态/待兑现.md"]

    for path, reason in selected:
        relative = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8")
        if relative.startswith("正文/") and len(content) > 5_000:
            content = "[仅保留上一章结尾]\n" + content[-5_000:]
        section_header = f"## 来源：{relative}\n\n- 选择原因：{reason}\n\n"
        remaining = max_chars - used - len(section_header)
        if remaining <= 200:
            break
        if len(content) > remaining:
            content = content[: max(0, remaining - 20)] + "\n\n[已按预算截断]"
        section = section_header + content.strip() + "\n"
        output_parts.append(section)
        used += len(section)
        included.append(relative)

    return "\n".join(output_parts).rstrip() + "\n", included


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建下一章所需的最小上下文包")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", type=int, default=0)
    parser.add_argument("--query", default="")
    parser.add_argument("--max-chars", type=int)
    parser.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.project_root).expanduser().resolve()
    try:
        project_meta, _ = parse_document(root / "作品.md")
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    default_budgets = {"light": 12_000, "standard": 24_000, "extended": 36_000}
    max_chars = args.max_chars or default_budgets.get(str(project_meta.get("complexity")), 24_000)
    if args.chapter < 0 or max_chars < 2_000:
        print(json.dumps({"ok": False, "error": "章节号不能为负，字符预算不能少于 2000"}, ensure_ascii=False))
        return 2
    index_root = (root / "索引").resolve()
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else index_root / f"context-pack-{args.chapter or 'current'}.md"
    )
    try:
        ensure_within(index_root, output)
        if output.suffix.lower() != ".md":
            raise ValueError("上下文包输出必须是 索引/ 内的 .md 文件")
        content, included = build_context(root, args.chapter, args.query, max_chars)
        atomic_write_text(output, content)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "output": str(output), "included": included}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
