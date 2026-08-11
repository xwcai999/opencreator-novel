#!/usr/bin/env python3
"""Zero-dependency lexical retrieval for long fiction projects."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from studio_common import atomic_write_json, ensure_within, markdown_files, parse_document


def tokenize(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    english = re.findall(r"[a-z0-9]{2,}", normalized)
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", normalized)
    grams: list[str] = []
    for run in cjk_runs:
        if len(run) == 1:
            grams.append(run)
        else:
            grams.extend(run[index : index + 2] for index in range(len(run) - 1))
            if len(run) >= 3:
                grams.extend(run[index : index + 3] for index in range(len(run) - 2))
    return english + grams


def _snippet(text: str, terms: list[str], limit: int = 480) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    positions = [compact.lower().find(term.lower()) for term in terms if term]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - limit // 3)
    end = min(len(compact), start + limit)
    prefix = "…" if start else ""
    suffix = "…" if end < len(compact) else ""
    return prefix + compact[start:end] + suffix


def retrieve(root: Path, query: str, top_k: int = 6) -> dict[str, Any]:
    root = root.expanduser().resolve()
    query_tokens = set(tokenize(query))
    direct_terms = [term for term in re.split(r"[\s,，。；;]+", query) if term]
    results: list[dict[str, Any]] = []

    for path in markdown_files(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        try:
            meta, body = parse_document(path)
        except ValueError:
            continue
        if meta.get("type") == "style-profile" and meta.get("status") != "active":
            continue
        haystack = f"{relative}\n{meta.get('id', '')}\n{meta.get('name', '')}\n{meta.get('title', '')}\n{body}"
        doc_tokens = set(tokenize(haystack))
        overlap = len(query_tokens & doc_tokens)
        direct_hits = sum(1 for term in direct_terms if term.lower() in haystack.lower())
        id_hits = sum(
            1
            for value in (meta.get("id"), meta.get("name"), meta.get("title"))
            if value and str(value).lower() in query.lower()
        )
        path_bonus = 2 if any(term.lower() in relative.lower() for term in direct_terms) else 0
        score = overlap + direct_hits * 3 + id_hits * 5 + path_bonus
        if score <= 0:
            continue
        results.append(
            {
                "path": relative,
                "type": meta.get("type", ""),
                "id": meta.get("id", ""),
                "score": score,
                "reason": {
                    "token_overlap": overlap,
                    "direct_hits": direct_hits,
                    "entity_hits": id_hits,
                    "path_bonus": path_bonus,
                },
                "snippet": _snippet(body, direct_terms),
            }
        )

    results.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    return {
        "ok": True,
        "method": "lexical-cjk-ngram-entity-overlap",
        "query": query,
        "top_k": top_k,
        "results": results[:top_k],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检索与剧情任务相关的 Novel Studio 文件片段")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.top_k < 1 or args.top_k > 50:
        print(json.dumps({"ok": False, "error": "top-k 必须在 1 到 50 之间"}, ensure_ascii=False))
        return 2
    root = Path(args.project_root).expanduser().resolve()
    try:
        result = retrieve(root, args.query, args.top_k)
        if args.output:
            output = ensure_within(root / "索引", Path(args.output).expanduser().resolve())
            if output.suffix.lower() != ".json":
                raise ValueError("检索输出必须是 索引/ 内的 .json 文件")
            atomic_write_json(output, result)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
