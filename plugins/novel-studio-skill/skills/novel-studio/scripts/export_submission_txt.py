#!/usr/bin/env python3
"""从 Novel Studio 权威章节导出可被平台稳定分章的 TXT。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from studio_common import chapter_number, ensure_within, parse_document


HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*(?:\r?\n|$)")


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _clean_body(body: str, *, number: int, title: str) -> str:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n").lstrip("\n")
    match = HEADING_RE.match(normalized)
    if match:
        heading = match.group(1).strip()
        accepted = {title, f"第{number}章 {title}", f"第{number}章　{title}"}
        if heading in accepted:
            normalized = normalized[match.end():].lstrip("\n")
    return normalized.rstrip()


def export_submission_txt(
    project_root: str | Path,
    output: str | Path,
    *,
    require_accepted: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    output_path = Path(output).expanduser()
    if not output_path.is_absolute():
        output_path = root / output_path
    output_path = ensure_within(root, output_path)
    if output_path.suffix.lower() != ".txt":
        raise ValueError("输出文件扩展名必须为 .txt")
    protected = {root / "正文", root / "作品.md", root / "当前状态.md"}
    if any(output_path == item or item in output_path.parents for item in protected):
        raise ValueError("输出路径不得位于正文目录，也不得覆盖权威项目文件")
    body_root = root / "正文"
    errors: list[str] = []
    chapters: list[dict[str, Any]] = []

    if not body_root.is_dir():
        errors.append("项目缺少正文目录")
    else:
        for path in sorted(body_root.rglob("*.md")):
            try:
                safe_path = ensure_within(root, path)
            except ValueError:
                errors.append(f"章节路径越界: {path}")
                continue
            if path.is_symlink() or safe_path.is_symlink():
                errors.append(f"章节不得为符号链接: {path.relative_to(root).as_posix()}")
                continue
            try:
                metadata, body = parse_document(path)
            except (OSError, UnicodeError, ValueError) as exc:
                errors.append(f"无法解析 {path.relative_to(root).as_posix()}: {exc}")
                continue
            if metadata.get("type") != "chapter":
                continue
            raw_number = metadata.get("number")
            if isinstance(raw_number, bool) or not isinstance(raw_number, int):
                number = 0
            else:
                number = chapter_number(path, metadata)
            title = str(metadata.get("title") or "").strip()
            status = str(metadata.get("status") or "").strip()
            label = path.relative_to(root).as_posix()
            if number <= 0:
                errors.append(f"章节编号必须为正整数: {label}")
            if not title or "\n" in title or "\r" in title:
                errors.append(f"章节标题必须为非空单行文本: {label}")
            if require_accepted and status != "accepted":
                errors.append(f"完本导出要求章节 status=accepted: {label}")
            chapters.append({"number": number, "title": title, "source": label, "body": _clean_body(body, number=number, title=title)})

    chapters.sort(key=lambda item: (item["number"], item["source"]))
    numbers = [item["number"] for item in chapters]
    if not chapters:
        errors.append("正文目录中没有 type=chapter 的章节")
    elif numbers != list(range(1, len(chapters) + 1)):
        errors.append(f"章节编号必须从 1 连续且不得重复，当前为: {numbers}")

    result: dict[str, Any] = {
        "ok": not errors,
        "output": output_path.relative_to(root).as_posix(),
        "chapter_count": len(chapters),
        "chapters": [{key: item[key] for key in ("number", "title", "source")} for item in chapters],
        "encoding": "utf-8",
        "bom": False,
        "line_ending": "CRLF",
        "errors": errors,
        "warnings": [],
    }
    if errors:
        return result

    sections = [f"第{item['number']}章 {item['title']}\n\n{item['body']}".rstrip() for item in chapters]
    text = "\n\n".join(sections) + "\n"
    encoded = text.replace("\n", "\r\n").encode("utf-8")
    _atomic_write_bytes(output_path, encoded)
    result["content_sha256"] = hashlib.sha256(encoded).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="导出可稳定分章的投稿 TXT")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True, help="须位于项目目录内；相对路径以项目根目录解析")
    parser.add_argument("--allow-unaccepted", action="store_true", help="允许导出未验收章节")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = export_submission_txt(
            args.project_root,
            args.output,
            require_accepted=not args.allow_unaccepted,
        )
    except (OSError, ValueError) as exc:
        result = {"ok": False, "errors": [str(exc)], "warnings": []}
        code = 2
    else:
        code = 0 if result["ok"] else 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else ("导出成功" if result["ok"] else "导出失败：" + "；".join(result["errors"])))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
