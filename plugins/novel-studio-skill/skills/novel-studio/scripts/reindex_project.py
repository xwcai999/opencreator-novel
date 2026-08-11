#!/usr/bin/env python3
"""Build a deterministic, disposable index from authoritative Markdown files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from studio_common import atomic_write_json, ensure_within, markdown_files, parse_document, sha256_text
from validate_project import validate_project


def build_index(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    validation = validate_project(root)
    if not validation["ok"]:
        raise ValueError("项目硬门禁未通过，拒绝覆盖索引: " + "；".join(validation["errors"]))

    project_meta, _ = parse_document(root / "作品.md")
    documents: list[dict[str, Any]] = []
    for path in markdown_files(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        meta, _ = parse_document(path)
        documents.append(
            {
                "path": relative,
                "type": meta.get("type", ""),
                "id": meta.get("id", ""),
                "name": meta.get("name") or meta.get("title") or path.stem,
                "number": meta.get("number", ""),
                "status": meta.get("status", ""),
                "sha256": sha256_text(text),
            }
        )
    documents.sort(key=lambda item: item["path"])

    counts: dict[str, int] = {}
    for document in documents:
        doc_type = str(document["type"] or "untyped")
        counts[doc_type] = counts.get(doc_type, 0) + 1

    content_signature = sha256_text(
        "\n".join(f"{item['path']}:{item['sha256']}" for item in documents)
    )
    return {
        "index-version": 1,
        "project": {
            "id": project_meta.get("id"),
            "title": project_meta.get("title"),
            "scope": project_meta.get("scope"),
            "complexity": project_meta.get("complexity"),
            "primary-driver": project_meta.get("primary-driver"),
            "secondary-driver": project_meta.get("secondary-driver") or "",
        },
        "content-signature": content_signature,
        "counts": dict(sorted(counts.items())),
        "documents": documents,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 Markdown 权威数据重建 Novel Studio 索引")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.project_root).expanduser().resolve()
    index_root = (root / "索引").resolve()
    output = Path(args.output).expanduser().resolve() if args.output else index_root / "project-index.json"
    try:
        ensure_within(index_root, output)
        if output.suffix.lower() != ".json":
            raise ValueError("索引输出必须是 索引/ 内的 .json 文件")
        index = build_index(root)
        atomic_write_json(output, index)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "content_signature": index["content-signature"],
                "documents": len(index["documents"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
