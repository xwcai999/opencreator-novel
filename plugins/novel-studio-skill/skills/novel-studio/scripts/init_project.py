#!/usr/bin/env python3
"""Initialize a new Novel Studio project without overwriting existing files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from studio_common import (
    COMPLEXITIES,
    DRIVERS,
    SCOPES,
    atomic_write_text,
    ensure_empty_target,
    project_id,
    render_template,
    validate_book_title,
)

SCRIPT_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = SCRIPT_ROOT.parent / "assets" / "project-template"

PROFILE_DEFAULTS = {
    "short": {"target_words": 20_000, "planning_horizon": "full"},
    "medium": {"target_words": 100_000, "planning_horizon": "arc"},
    "long": {"target_words": 1_000_000, "planning_horizon": "rolling"},
}

TEMPLATES = {
    "作品.md": "作品.md.tmpl",
    "设定/题材定位.md": "题材定位.md.tmpl",
    "设定/读者契约.md": "读者契约.md.tmpl",
    "设定/文风档案.md": "文风档案.md.tmpl",
    "大纲/总纲.md": "总纲.md.tmpl",
    "状态/当前状态.md": "当前状态.md.tmpl",
    "状态/时间线.md": "时间线.md.tmpl",
    "状态/关系.md": "关系.md.tmpl",
    "状态/待兑现.md": "待兑现.md.tmpl",
}

DIRECTORIES = (
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="初始化 Novel Studio 小说项目")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--scope", choices=sorted(SCOPES), required=True)
    parser.add_argument("--complexity", choices=sorted(COMPLEXITIES), required=True)
    parser.add_argument("--primary-driver", choices=sorted(DRIVERS), required=True)
    parser.add_argument("--secondary-driver", choices=[""] + sorted(DRIVERS), default="")
    parser.add_argument("--target-words", type=int)
    parser.add_argument("--serialization", action="store_true")
    return parser


def initialize(args: argparse.Namespace) -> dict[str, object]:
    root = Path(args.project_root).expanduser().resolve()
    ensure_empty_target(root)
    title = validate_book_title(args.title)
    if args.secondary_driver and args.secondary_driver == args.primary_driver:
        raise ValueError("副驱动不能与主驱动相同")
    target_words = args.target_words or PROFILE_DEFAULTS[args.scope]["target_words"]
    if target_words < 1_000:
        raise ValueError("目标字数不能少于 1000")

    root.mkdir(parents=True, exist_ok=True)
    for relative in DIRECTORIES:
        (root / relative).mkdir(parents=True, exist_ok=True)

    pid = project_id(title)
    values = {
        "schema_version": "2",
        "project_id": pid,
        "title": title.replace('"', "'"),
        "scope": args.scope,
        "complexity": args.complexity,
        "primary_driver": args.primary_driver,
        "secondary_driver": args.secondary_driver,
        "secondary_driver_display": args.secondary_driver or "无",
        "target_words": str(target_words),
        "serialization": str(bool(args.serialization)).lower(),
        "planning_horizon": str(PROFILE_DEFAULTS[args.scope]["planning_horizon"]),
        "continuity_level": args.complexity,
    }

    created: list[str] = []
    for relative, template_name in TEMPLATES.items():
        target = root / relative
        content = render_template(TEMPLATE_ROOT / template_name, values)
        atomic_write_text(target, content)
        created.append(relative)

    return {
        "ok": True,
        "project_root": str(root),
        "project_id": pid,
        "scope": args.scope,
        "complexity": args.complexity,
        "primary_driver": args.primary_driver,
        "secondary_driver": args.secondary_driver,
        "created": created,
    }


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = initialize(args)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
