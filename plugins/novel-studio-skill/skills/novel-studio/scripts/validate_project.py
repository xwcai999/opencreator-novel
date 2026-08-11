#!/usr/bin/env python3
"""Validate objective Novel Studio project invariants without modifying the project."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from expectation_ledger import audit_ledger
from studio_common import (
    COMPLEXITIES,
    DRIVERS,
    SCOPES,
    as_list,
    atomic_write_json,
    chapter_number,
    ensure_within,
    is_kebab_id,
    markdown_files,
    parse_document,
    sha256_text,
    text_units,
    validate_book_title,
)

CHAPTER_STATUSES = {"draft", "author-reviewed", "reader-reviewed", "revised", "accepted"}

REQUIRED_FILES = (
    "作品.md",
    "设定/题材定位.md",
    "设定/读者契约.md",
    "大纲/总纲.md",
    "状态/当前状态.md",
    "状态/时间线.md",
    "状态/关系.md",
    "状态/待兑现.md",
)

REQUIRED_DIRS = (
    "设定/角色",
    "设定/世界观",
    "大纲/卷纲",
    "大纲/细纲",
    "正文",
    "状态",
    "索引",
    "报告",
    "封面",
)

PLACEHOLDER_PATTERNS = (
    re.compile(r"(?im)^\s*TODO\b"),
    re.compile(r"\[待写\]"),
    re.compile(r"NOVEL_FLOW_STUB"),
    re.compile(r"(?m)^\s*\[(?:说明|分析|角色定位)\]"),
)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _add_required(meta: dict[str, Any], fields: tuple[str, ...], label: str, errors: list[str]) -> None:
    for field in fields:
        if meta.get(field) in (None, ""):
            errors.append(f"{label}: 缺少字段 {field}")


def validate_project(root: Path) -> dict[str, object]:
    root = root.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    documents: list[dict[str, Any]] = []

    if not root.is_dir():
        return {"ok": False, "project_root": str(root), "errors": ["项目目录不存在"], "warnings": []}

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"缺少必需文件: {relative}")
    for relative in REQUIRED_DIRS:
        if not (root / relative).is_dir():
            errors.append(f"缺少必需目录: {relative}")
    if errors:
        return {"ok": False, "project_root": str(root), "errors": errors, "warnings": warnings}

    try:
        project_meta, _ = parse_document(root / "作品.md")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        project_meta = {}

    _add_required(
        project_meta,
        ("schema-version", "type", "id", "title", "scope", "complexity", "primary-driver"),
        "作品.md",
        errors,
    )
    schema_version = _int(project_meta.get("schema-version"), 0)
    if schema_version not in {1, 2}:
        errors.append("作品.md: schema-version 必须为 1（兼容旧项目）或 2")
    elif schema_version == 1:
        warnings.append("作品.md: schema-version=1 为兼容模式；逐章审查证据与接受边界只提示、不强制")
    if project_meta.get("type") != "novel-project":
        errors.append("作品.md: type 必须为 novel-project")
    try:
        validate_book_title(str(project_meta.get("title") or ""))
    except ValueError as exc:
        errors.append(f"作品.md: {exc}")
    if project_meta.get("scope") not in SCOPES:
        errors.append(f"作品.md: 非法 scope {project_meta.get('scope')!r}")
    if project_meta.get("complexity") not in COMPLEXITIES:
        errors.append(f"作品.md: 非法 complexity {project_meta.get('complexity')!r}")
    primary = project_meta.get("primary-driver")
    secondary = project_meta.get("secondary-driver") or ""
    if primary not in DRIVERS:
        errors.append(f"作品.md: 非法 primary-driver {primary!r}")
    if secondary and secondary not in DRIVERS:
        errors.append(f"作品.md: 非法 secondary-driver {secondary!r}")
    if secondary and secondary == primary:
        errors.append("作品.md: 主副驱动不能相同")
    if project_meta.get("cover-author-attribution") != "forbidden":
        errors.append("作品.md: cover-author-attribution 必须为 forbidden")

    ids: dict[str, str] = {}
    characters: dict[str, dict[str, Any]] = {}
    locations: set[str] = set()
    arcs: set[str] = set()
    chapters: list[dict[str, Any]] = []
    chapter_outlines: list[dict[str, Any]] = []
    chapter_numbers: dict[int, str] = {}

    for path in markdown_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            meta, body = parse_document(path)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        doc_type = str(meta.get("type") or "")
        doc_id = meta.get("id")
        if doc_id not in (None, ""):
            if not is_kebab_id(doc_id):
                errors.append(f"{relative}: id 必须为 ASCII kebab-case，当前为 {doc_id!r}")
            elif doc_id in ids:
                errors.append(f"ID 重复 {doc_id}: {ids[doc_id]} 与 {relative}")
            else:
                ids[str(doc_id)] = relative

        record = {"path": relative, "type": doc_type, "id": doc_id, "metadata": meta, "body": body}
        documents.append(record)

        if doc_type == "character":
            _add_required(meta, ("id", "name", "status"), relative, errors)
            if doc_id:
                characters[str(doc_id)] = meta
        elif doc_type == "location":
            _add_required(meta, ("id", "name"), relative, errors)
            if doc_id:
                locations.add(str(doc_id))
        elif doc_type == "arc":
            _add_required(meta, ("id", "name"), relative, errors)
            if doc_id:
                arcs.add(str(doc_id))
        elif doc_type == "chapter":
            _add_required(meta, ("id", "number", "title", "status"), relative, errors)
            status = str(meta.get("status") or "").strip().lower()
            if status not in CHAPTER_STATUSES:
                message = f"{relative}: 非法章节 status {status!r}"
                (errors if schema_version >= 2 else warnings).append(message)
            number = chapter_number(path, meta)
            if number <= 0:
                errors.append(f"{relative}: 章节号必须大于 0")
            elif number in chapter_numbers:
                errors.append(f"章节号重复 {number}: {chapter_numbers[number]} 与 {relative}")
            else:
                chapter_numbers[number] = relative
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern.search(body):
                    errors.append(f"{relative}: 正文含生成占位符或分析标记")
                    break
            declared = _int(meta.get("word-count"), -1)
            actual = text_units(body)
            if declared >= 0 and declared != actual:
                warnings.append(f"{relative}: word-count={declared}，实际计数={actual}")
            record["number"] = number
            record["status"] = status
            chapters.append(record)
        elif doc_type == "chapter-outline":
            _add_required(meta, ("id", "title"), relative, errors)
            outline_number = chapter_number(path, meta)
            if outline_number <= 0:
                errors.append(f"{relative}: 无法从 frontmatter 或文件名确定章纲编号")
            record["number"] = outline_number
            chapter_outlines.append(record)

    for chapter in chapters:
        meta = chapter["metadata"]
        relative = chapter["path"]
        number = int(chapter["number"])
        present = {str(item) for item in as_list(meta.get("characters")) if item}
        mentions = {str(item) for item in as_list(meta.get("mentions")) if item}
        allowed_dead = {str(item) for item in as_list(meta.get("allow-deceased-present")) if item}
        for char_id in sorted(present | mentions):
            if char_id not in characters:
                errors.append(f"{relative}: 引用不存在的角色 {char_id}")
        pov = str(meta.get("pov") or "")
        if pov and pov not in characters:
            errors.append(f"{relative}: POV 角色不存在 {pov}")
        for location_id in (str(item) for item in as_list(meta.get("locations")) if item):
            if location_id not in locations:
                errors.append(f"{relative}: 引用不存在的地点 {location_id}")
        for arc_id in (str(item) for item in as_list(meta.get("arcs-advanced")) if item):
            if arc_id not in arcs:
                errors.append(f"{relative}: 引用不存在的剧情线 {arc_id}")
        for char_id in sorted(present):
            character = characters.get(char_id, {})
            status = str(character.get("status") or "").lower()
            died_in = _int(character.get("died-in"), 0)
            if status in {"dead", "deceased", "死亡", "已故"} and died_in and number > died_in:
                if char_id not in allowed_dead:
                    errors.append(f"{relative}: 已死亡角色 {char_id} 在后续场景登场，未声明例外")

        if schema_version >= 2 and chapter.get("status") == "accepted":
            chapter_id = str(meta.get("id") or "")
            report_path = root / "报告" / "章节审查" / f"{chapter_id}.json"
            if not report_path.is_file():
                errors.append(f"{relative}: accepted 章节缺少审查证据 报告/章节审查/{chapter_id}.json")
            else:
                try:
                    review = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    errors.append(f"{report_path.relative_to(root).as_posix()}: 无法读取审查证据: {exc}")
                    review = {}
                if review.get("type") != "chapter-review" or review.get("chapter_id") != chapter_id:
                    errors.append(f"{report_path.relative_to(root).as_posix()}: 章节审查类型或 chapter_id 不匹配")
                if review.get("body_sha256") != sha256_text(str(chapter.get("body") or "")):
                    errors.append(f"{report_path.relative_to(root).as_posix()}: 正文哈希已变化，必须重新审查")
                rounds = _int(review.get("rounds"), 0)
                if rounds < 1 or rounds > 3:
                    errors.append(f"{report_path.relative_to(root).as_posix()}: rounds 必须在 1 到 3 之间")
                for key in ("author_review", "style_review", "independent_rereview"):
                    if review.get(key) != "passed":
                        errors.append(f"{report_path.relative_to(root).as_posix()}: {key} 必须为 passed")
                reader_result = review.get("first_reader_review")
                if reader_result != "passed":
                    if not (
                        reader_result == "overridden"
                        and review.get("user_override") is True
                        and str(review.get("override_reason") or "").strip()
                    ):
                        errors.append(
                            f"{report_path.relative_to(root).as_posix()}: 首次读者审查未通过且无明确用户覆盖理由"
                        )
                if review.get("result") != "accepted":
                    errors.append(f"{report_path.relative_to(root).as_posix()}: result 必须为 accepted")

    last_accepted = 0
    try:
        state_meta, _ = parse_document(root / "状态" / "当前状态.md")
        last_accepted = _int(state_meta.get("last-accepted-chapter"), 0)
        if last_accepted and last_accepted not in chapter_numbers:
            errors.append(f"状态/当前状态.md: last-accepted-chapter={last_accepted} 对应章节不存在")
        status_by_number = {int(chapter["number"]): chapter.get("status") for chapter in chapters}
        accepted_prefix = 0
        while status_by_number.get(accepted_prefix + 1) == "accepted":
            accepted_prefix += 1
        accepted_after_gap = sorted(
            number for number, status in status_by_number.items() if status == "accepted" and number > accepted_prefix
        )
        if schema_version >= 2:
            if accepted_after_gap:
                errors.append(f"章节接受顺序不连续，越过草稿接受了章节: {accepted_after_gap}")
            if last_accepted != accepted_prefix:
                errors.append(
                    f"状态/当前状态.md: last-accepted-chapter={last_accepted}，连续 accepted 前缀应为 {accepted_prefix}"
                )
        elif last_accepted != accepted_prefix:
            warnings.append(
                f"兼容项目接受边界不一致: last-accepted-chapter={last_accepted}，连续 accepted 前缀为 {accepted_prefix}"
            )
    except (OSError, ValueError) as exc:
        errors.append(str(exc))

    try:
        ledger = audit_ledger(root / "状态" / "待兑现.md", last_accepted + 1)
        errors.extend(str(item) for item in ledger["errors"])
        warnings.extend(str(item) for item in ledger["warnings"])
        expectation_count = len(ledger["items"])
        active_expectation_count = len(ledger["active_items"])
        ledger_ids = {str(item["id"]) for item in ledger["items"]}
        tracking_start = int(ledger.get("tracking_start_chapter") or 0)
        if schema_version >= 2 and int(ledger.get("ledger_version") or 0) == 2 and tracking_start > 0:
            for outline in chapter_outlines:
                number = int(outline.get("number") or 0)
                if number < tracking_start:
                    continue
                meta = outline["metadata"]
                relative = str(outline["path"])
                for field in (
                    "expectations-advanced", "expectations-fulfilled", "expectations-forbidden", "continuity-sources"
                ):
                    if field not in meta:
                        errors.append(f"{relative}: v2 连续性章纲缺少字段 {field}")
                        continue
                    if field == "continuity-sources":
                        for source in (str(item) for item in as_list(meta.get(field)) if item):
                            source_path = (root / source).resolve()
                            try:
                                ensure_within(root, source_path)
                            except ValueError as exc:
                                errors.append(f"{relative}: continuity-sources {exc}")
                                continue
                            if source_path.suffix.lower() != ".md" or not source_path.is_file():
                                errors.append(f"{relative}: continuity-sources 引用不存在的 Markdown {source}")
                        continue
                    for item_id in (str(item) for item in as_list(meta.get(field)) if item):
                        if item_id not in ledger_ids:
                            errors.append(f"{relative}: {field} 引用不存在的待兑现 ID {item_id}")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
        expectation_count = 0
        active_expectation_count = 0

    return {
        "ok": not errors,
        "project_root": str(root),
        "project": {
            "id": project_meta.get("id"),
            "title": project_meta.get("title"),
            "scope": project_meta.get("scope"),
            "complexity": project_meta.get("complexity"),
            "primary_driver": primary,
            "secondary_driver": secondary,
        },
        "counts": {
            "documents": len(documents),
            "characters": len(characters),
            "locations": len(locations),
            "arcs": len(arcs),
            "chapters": len(chapters),
            "expectations": expectation_count,
            "active_expectations": active_expectation_count,
        },
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 Novel Studio 项目结构和客观连续性")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.project_root).expanduser().resolve()
    try:
        result = validate_project(root)
        if args.output:
            output = ensure_within(root / "报告", Path(args.output).expanduser().resolve())
            if output.suffix.lower() != ".json":
                raise ValueError("校验报告必须是 报告/ 内的 .json 文件")
            atomic_write_json(output, result)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
