#!/usr/bin/env python3
"""Copy a legacy novel-planner project into a new OpenCreator Novel project."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from init_project import DIRECTORIES, PROFILE_DEFAULTS, TEMPLATE_ROOT, TEMPLATES
from studio_common import (
    COMPLEXITIES,
    DRIVERS,
    SCOPES,
    atomic_write_text,
    chapter_number,
    ensure_empty_target,
    project_id,
    render_template,
    stable_id,
    text_units,
    validate_book_title,
)


def _frontmatter(header: list[str], body: str) -> str:
    return "---\n" + "\n".join(header) + "\n---\n\n" + body.lstrip()


def _destination(relative: Path) -> Path:
    posix = relative.as_posix()
    mapping = {
        "追踪/上下文.md": Path("状态/当前状态.md"),
        "追踪/时间线.md": Path("状态/时间线.md"),
        "追踪/伏笔.md": Path("状态/待兑现.md"),
        "追踪/角色状态.md": Path("状态/角色状态.md"),
        "大纲/大纲.md": Path("大纲/总纲.md"),
    }
    if posix in mapping:
        return mapping[posix]
    if relative.parent.as_posix() == "大纲" and relative.name.startswith("卷纲_"):
        return Path("大纲/卷纲") / relative.name
    if relative.parent.as_posix() == "大纲" and relative.name.startswith("细纲_"):
        return Path("大纲/细纲") / relative.name
    return relative


def _normalize(relative: Path, text: str, pid: str, max_chapter: int) -> str:
    if text.replace("\r\n", "\n").startswith("---\n"):
        return text
    posix = relative.as_posix()
    if posix == "状态/当前状态.md":
        return _frontmatter(
            [
                "type: current-state",
                f"project: {pid}",
                "state-version: 1",
                f"current-chapter: {max_chapter}",
                f"last-accepted-chapter: {max_chapter}",
                'current-arc: ""',
            ],
            text,
        )
    fixed_types = {
        "状态/时间线.md": "timeline",
        "状态/关系.md": "relationship-state",
        "状态/待兑现.md": "expectation-ledger",
        "状态/角色状态.md": "character-state-ledger",
        "设定/题材定位.md": "genre-positioning",
        "设定/读者契约.md": "reader-contract",
        "大纲/总纲.md": "master-outline",
    }
    if posix in fixed_types:
        return _frontmatter([f"type: {fixed_types[posix]}", f"project: {pid}"], text)
    if posix.startswith("设定/角色/") and relative.suffix.lower() == ".md":
        doc_id = stable_id("character", relative.stem)
        return _frontmatter(
            ["type: character", f"id: {doc_id}", f'name: "{relative.stem}"', "status: active", "relationships: []"],
            text,
        )
    if posix.startswith("设定/世界观/") and relative.suffix.lower() == ".md":
        doc_id = stable_id("world", relative.stem)
        return _frontmatter(["type: world-note", f"id: {doc_id}", f'name: "{relative.stem}"'], text)
    if posix.startswith("大纲/卷纲/") and relative.suffix.lower() == ".md":
        doc_id = stable_id("arc", relative.stem)
        return _frontmatter(["type: arc", f"id: {doc_id}", f'name: "{relative.stem}"', "status: planning"], text)
    if posix.startswith("大纲/细纲/") and relative.suffix.lower() == ".md":
        number = chapter_number(relative)
        doc_id = f"chapter-outline-{number:03d}" if number else stable_id("chapter-outline", relative.stem)
        return _frontmatter(
            ["type: chapter-outline", f"id: {doc_id}", f"number: {number}", f'title: "{relative.stem}"'],
            text,
        )
    if posix.startswith("正文/") and relative.suffix.lower() == ".md":
        number = chapter_number(relative)
        doc_id = f"chapter-{number:03d}" if number else stable_id("chapter", relative.stem)
        title = re.sub(r"^第\d+章[_\s-]*", "", relative.stem) or relative.stem
        return _frontmatter(
            [
                "type: chapter",
                f"id: {doc_id}",
                f"number: {number}",
                f'title: "{title}"',
                "status: accepted",
                'pov: ""',
                "characters: []",
                "mentions: []",
                "locations: []",
                "arcs-advanced: []",
                "allow-deceased-present: []",
                f"word-count: {text_units(text)}",
            ],
            text,
        )
    if relative.suffix.lower() == ".md":
        doc_id = stable_id("legacy-note", posix)
        return _frontmatter(
            ["type: legacy-note", f"id: {doc_id}", f'name: "{relative.stem}"'],
            text,
        )
    return text


def migrate(args: argparse.Namespace) -> dict[str, object]:
    source = Path(args.source).expanduser().resolve()
    target = Path(args.target).expanduser().resolve()
    title = validate_book_title(args.title)
    if not source.is_dir():
        raise ValueError(f"源目录不存在: {source}")
    ensure_empty_target(target)
    try:
        target.relative_to(source)
    except ValueError:
        pass
    else:
        raise ValueError("目标目录不能位于源目录内部")

    skipped_legacy_covers = [
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.relative_to(source).parts[0] == "封面"
    ]
    source_files = [
        path
        for path in source.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.relative_to(source).parts[0] not in {".git", "索引", "报告", "封面"}
    ]
    max_chapter = max(
        (chapter_number(path) for path in source_files if path.relative_to(source).as_posix().startswith("正文/")),
        default=0,
    )
    destinations: dict[Path, Path] = {}
    for path in source_files:
        relative = path.relative_to(source)
        destination = _destination(relative)
        if destination in destinations:
            raise ValueError(f"迁移目标冲突: {relative} 与 {destinations[destination]} -> {destination}")
        destinations[destination] = relative

    target.mkdir(parents=True, exist_ok=True)
    for relative in DIRECTORIES:
        (target / relative).mkdir(parents=True, exist_ok=True)

    pid = project_id(title)
    copied: list[dict[str, str]] = []
    for destination, source_relative in sorted(destinations.items(), key=lambda item: item[0].as_posix()):
        source_path = source / source_relative
        target_path = target / destination
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix.lower() == ".md":
            text = source_path.read_text(encoding="utf-8")
            atomic_write_text(target_path, _normalize(destination, text, pid, max_chapter))
        else:
            shutil.copy2(source_path, target_path)
        copied.append({"source": source_relative.as_posix(), "target": destination.as_posix()})

    values = {
        "schema_version": "1",
        "project_id": pid,
        "title": title.replace('"', "'"),
        "scope": args.scope,
        "complexity": args.complexity,
        "primary_driver": args.primary_driver,
        "secondary_driver": args.secondary_driver,
        "secondary_driver_display": args.secondary_driver or "无",
        "target_words": str(args.target_words or PROFILE_DEFAULTS[args.scope]["target_words"]),
        "serialization": str(bool(args.serialization)).lower(),
        "planning_horizon": str(PROFILE_DEFAULTS[args.scope]["planning_horizon"]),
        "continuity_level": args.complexity,
    }
    added: list[str] = []
    for relative, template_name in TEMPLATES.items():
        target_path = target / relative
        if not target_path.exists():
            atomic_write_text(target_path, render_template(TEMPLATE_ROOT / template_name, values))
            added.append(relative)
        elif target_path.suffix.lower() == ".md":
            current = target_path.read_text(encoding="utf-8")
            normalized = _normalize(Path(relative), current, pid, max_chapter)
            if normalized != current:
                atomic_write_text(target_path, normalized)

    report_lines = [
        "# 迁移报告",
        "",
        f"- 源目录：`{source}`",
        f"- 目标目录：`{target}`",
        "- 源项目修改：否",
        f"- 复制或映射文件：{len(copied)}",
        f"- 新增标准文件：{len(added)}",
        f"- 隔离未迁移的旧封面：{len(skipped_legacy_covers)}",
        "- 封面状态：未验证；必须按无笔名封面工作流重新生成",
        "",
        "## 映射记录",
        "",
    ]
    report_lines.extend(f"- `{item['source']}` → `{item['target']}`" for item in copied)
    if skipped_legacy_covers:
        report_lines.extend(["", "## 未迁移的旧封面", ""])
        report_lines.extend(f"- `{item}`" for item in skipped_legacy_covers)
    atomic_write_text(target / "报告" / "迁移报告.md", "\n".join(report_lines) + "\n")
    return {
        "ok": True,
        "source": str(source),
        "target": str(target),
        "source_modified": False,
        "copied": copied,
        "added": added,
        "skipped_legacy_covers": skipped_legacy_covers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="把旧 novel-planner 项目安全迁移到新目录")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--scope", choices=sorted(SCOPES), default="long")
    parser.add_argument("--complexity", choices=sorted(COMPLEXITIES), default="standard")
    parser.add_argument("--primary-driver", choices=sorted(DRIVERS), default="growth")
    parser.add_argument("--secondary-driver", choices=[""] + sorted(DRIVERS), default="")
    parser.add_argument("--target-words", type=int)
    parser.add_argument("--serialization", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.secondary_driver and args.secondary_driver == args.primary_driver:
        print(json.dumps({"ok": False, "error": "副驱动不能与主驱动相同"}, ensure_ascii=False))
        return 2
    try:
        result = migrate(args)
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
