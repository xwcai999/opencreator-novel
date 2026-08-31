#!/usr/bin/env python3
"""通过受控 CLI 把蛙蛙投稿包交给本机页面预填引擎。"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


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
        completed = subprocess.run(command, check=False)
        return completed.returncode
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


