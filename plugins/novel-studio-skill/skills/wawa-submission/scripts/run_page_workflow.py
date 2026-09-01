#!/usr/bin/env python3
"""通过受控 CLI 把蛙蛙投稿包交给本机页面预填引擎。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from validate_submission import validate_submission


ALLOWED_ACTIONS = {"dry-run", "prepare", "login", "campaigns", "taxonomy-sync", "status", "cancel"}
DEFAULT_ENGINE = Path(r"D:\claw\scripts\wawa-submission-playwright\wawa-submission-playwright.mjs")


def resolve_engine(explicit: str = "") -> Path:
    candidate = explicit or os.environ.get("WAWA_SUBMISSION_ENGINE", "") or str(DEFAULT_ENGINE)
    path = Path(candidate).expanduser().resolve()
    if path.name != "wawa-submission-playwright.mjs":
        raise ValueError("页面引擎入口文件名必须为 wawa-submission-playwright.mjs")
    if not path.is_file():
        raise FileNotFoundError(f"页面引擎不存在: {path}")
    return path


def build_command(args: argparse.Namespace, engine: Path) -> list[str]:
    action = args.action
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"不支持的页面动作: {action}")
    command = [args.node, str(engine), f"--{action}"]
    if action in {"dry-run", "prepare"}:
        if not args.metadata:
            raise ValueError(f"{action} 必须提供 --metadata")
        metadata = Path(args.metadata).expanduser().resolve()
        if not metadata.is_file():
            raise FileNotFoundError(f"投稿包不存在: {metadata}")
        command.extend(["--metadata", str(metadata)])
    if args.config:
        command.extend(["--config", str(Path(args.config).expanduser().resolve())])
    if args.snapshot:
        command.extend(["--snapshot", str(Path(args.snapshot).expanduser().resolve())])
    if args.campaign_code:
        command.extend(["--campaign-code", args.campaign_code])
    if args.run_id:
        command.extend(["--run-id", args.run_id])
    if args.allow_live:
        command.append("--allow-live")
    if action in {"prepare", "login", "campaigns", "taxonomy-sync"} and not args.allow_live:
        raise ValueError(f"{action} 涉及真实页面，必须显式提供 --allow-live")
    return command


def preflight_execution_package(metadata_path: str | Path) -> Mapping[str, Any]:
    """在启动页面引擎前执行 v2 契约和真实文件内容预检。"""

    path = Path(metadata_path).expanduser().resolve(strict=False)
    try:
        with path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取投稿包: {exc.__class__.__name__}") from exc
    if not isinstance(metadata, Mapping):
        raise ValueError("投稿包 JSON 须为对象")
    if metadata.get("schema_version") != 2:
        raise ValueError("页面工作流只消费 schema v2；请先将 v1/无版本材料升级为 v2 投稿包")

    # v2 文件路径必须为绝对路径；Node 引擎随后再按 storage.allowedRoots
    # 执行 containment 校验。此处负责补齐真实图片/DOCX 解析与业务契约预检。
    result = validate_submission(metadata)
    if not result.get("ok"):
        issues = [*(result.get("errors") or []), *(result.get("blockers") or [])]
        summary = "；".join(str(item) for item in issues[:5]) or "投稿包未通过本地预检"
        raise ValueError(f"投稿包预检失败: {summary}")
    return result


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="蛙蛙投稿 Skill 页面工作流入口（不支持最终提交）")
    value.add_argument("action", choices=sorted(ALLOWED_ACTIONS))
    value.add_argument("--metadata")
    value.add_argument("--campaign-code", default="")
    value.add_argument("--run-id", default="")
    value.add_argument("--config", default="")
    value.add_argument("--snapshot", default="")
    value.add_argument("--engine", default="")
    value.add_argument("--node", default="node")
    value.add_argument("--allow-live", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        engine = resolve_engine(args.engine)
        command = build_command(args, engine)
        if args.action in {"dry-run", "prepare"}:
            preflight_execution_package(args.metadata)
        completed = subprocess.run(command, check=False)
        return completed.returncode
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

