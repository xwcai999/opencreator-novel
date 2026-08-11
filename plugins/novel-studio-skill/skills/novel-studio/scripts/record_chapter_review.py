#!/usr/bin/env python3
"""为完成审查的章节记录固定位置、绑定正文哈希的接受证据。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from studio_common import atomic_write_json, chapter_number, parse_document, sha256_text


def find_chapter(root: Path, number: int) -> tuple[Path, dict[str, object], str]:
    matches: list[tuple[Path, dict[str, object], str]] = []
    for path in (root / "正文").rglob("*.md"):
        metadata, body = parse_document(path)
        if metadata.get("type") == "chapter" and chapter_number(path, metadata) == number:
            matches.append((path, metadata, body))
    if len(matches) != 1:
        raise ValueError(f"章节号 {number} 应唯一匹配一个正文文件，实际为 {len(matches)}")
    return matches[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="记录逐章审查接受证据；不修改正文或权威状态")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--author-passed", action="store_true")
    reader = parser.add_mutually_exclusive_group(required=True)
    reader.add_argument("--reader-passed", action="store_true")
    reader.add_argument("--user-override", action="store_true")
    parser.add_argument("--override-reason")
    parser.add_argument("--style-passed", action="store_true")
    parser.add_argument("--rereview-passed", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        root = Path(args.project_root).expanduser().resolve()
        if args.chapter < 1:
            raise ValueError("章节号必须大于 0")
        if args.rounds < 1 or args.rounds > 3:
            raise ValueError("审查轮次必须在 1 到 3 之间")
        if not (args.author_passed and args.style_passed and args.rereview_passed):
            raise ValueError("作者审查、文体审查和独立复审必须全部通过")
        if args.user_override and not str(args.override_reason or "").strip():
            raise ValueError("覆盖首次读者门禁时必须提供 --override-reason")
        path, metadata, body = find_chapter(root, args.chapter)
        chapter_id = str(metadata.get("id") or "")
        if not chapter_id:
            raise ValueError(f"{path}: 缺少章节 id")
        output = root / "报告" / "章节审查" / f"{chapter_id}.json"
        if output.exists():
            raise ValueError(f"审查证据已存在，拒绝静默覆盖: {output}")
        payload = {
            "schema_version": 1,
            "type": "chapter-review",
            "chapter_id": chapter_id,
            "chapter_number": args.chapter,
            "chapter_path": path.relative_to(root).as_posix(),
            "body_sha256": sha256_text(body),
            "rounds": args.rounds,
            "author_review": "passed",
            "first_reader_review": "overridden" if args.user_override else "passed",
            "style_review": "passed",
            "independent_rereview": "passed",
            "user_override": bool(args.user_override),
            "override_reason": str(args.override_reason or "").strip(),
            "result": "accepted",
        }
        atomic_write_json(output, payload)
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "output": str(output), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
