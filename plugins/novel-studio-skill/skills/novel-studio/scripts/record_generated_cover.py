#!/usr/bin/env python3
"""Record a model-native-title cover manifest without changing image pixels."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from studio_common import (
    atomic_write_json,
    ensure_within,
    parse_document,
    read_text,
    sha256_text,
    validate_book_title,
)


NATIVE_TITLE_MARKERS = ("一次生成", "直接生成完整封面", "model-native", "in-image title")
TITLE_ONLY_MARKERS = ("只允许", "不得出现任何其他文字", "only visible text", "no other visible text")
NO_ATTRIBUTION_MARKERS = ("无作者名", "无笔名", "无署名", "no author", "no signature")
NO_WATERMARK_MARKERS = ("无水印", "no watermark")
FORBIDDEN_FILENAME_MARKERS = ("作者", "笔名", "署名", "author", "byline", "pen-name", "penname")
PNG_METADATA_CHUNKS = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def inspect_png(path: Path) -> tuple[int, int, list[str]]:
    raw = path.read_bytes()
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("原生书名封面必须是有效 PNG")
    offset = 8
    width = height = 0
    metadata_chunks: list[str] = []
    saw_iend = False
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        chunk_type = raw[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(raw):
            raise ValueError("PNG 数据块越界或文件不完整")
        data = raw[offset + 8 : offset + 8 + length]
        if chunk_type == b"IHDR":
            if len(data) != 13:
                raise ValueError("PNG IHDR 长度无效")
            width, height = struct.unpack(">II", data[:8])
        if chunk_type in PNG_METADATA_CHUNKS:
            metadata_chunks.append(chunk_type.decode("ascii"))
        offset = end
        if chunk_type == b"IEND":
            saw_iend = True
            break
    if not saw_iend or width <= 0 or height <= 0:
        raise ValueError("PNG 缺少有效 IHDR/IEND")
    return width, height, metadata_chunks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="记录由图片模型一次生成画面与书名的封面清单")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--output", help="默认取封面同名 .manifest.json")
    parser.add_argument("--replace", action="store_true", help="允许原子替换既有清单，不修改图片")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        project_root = Path(args.project_root).expanduser().resolve()
        project_meta, _ = parse_document(project_root / "作品.md")
        title = validate_book_title(str(project_meta.get("title") or ""))
        cover_root = (project_root / "封面").resolve()
        image = ensure_within(cover_root, Path(args.image).expanduser().resolve())
        prompt_path = ensure_within(cover_root, Path(args.prompt_file).expanduser().resolve())
        output = ensure_within(
            cover_root,
            Path(args.output).expanduser().resolve() if args.output else image.with_suffix(".manifest.json"),
        )
        if output.suffix.lower() != ".json":
            raise ValueError("封面清单必须是 封面/ 内的 .json 文件")
        if output.exists() and not args.replace:
            raise ValueError(f"封面清单已存在，拒绝静默覆盖: {output}")
        if image.suffix.lower() != ".png" or not image.is_file():
            raise ValueError(f"封面 PNG 不存在: {image}")
        if not prompt_path.is_file():
            raise ValueError(f"封面提示词不存在: {prompt_path}")
        prompt = read_text(prompt_path)
        if title not in prompt:
            raise ValueError("封面提示词必须逐字包含 作品.md 中的规范书名")
        if not _contains_any(prompt, NATIVE_TITLE_MARKERS):
            raise ValueError("封面提示词必须明确要求书名与画面一次生成")
        if not _contains_any(prompt, TITLE_ONLY_MARKERS):
            raise ValueError("封面提示词必须明确只允许规范书名作为可见文字")
        if not _contains_any(prompt, NO_ATTRIBUTION_MARKERS):
            raise ValueError("封面提示词必须禁止作者名、笔名或署名")
        if not _contains_any(prompt, NO_WATERMARK_MARKERS):
            raise ValueError("封面提示词必须禁止水印")
        if any(marker.casefold() in image.name.casefold() for marker in FORBIDDEN_FILENAME_MARKERS):
            raise ValueError("封面文件名含作者/笔名/署名标记")
        width, height, metadata_chunks = inspect_png(image)
        if metadata_chunks:
            raise ValueError(f"封面 PNG 含文本/EXIF 元数据块: {metadata_chunks}")
        image_bytes = image.read_bytes()
        payload = {
            "schema_version": 2,
            "type": "cover-manifest",
            "image": image.name,
            "prompt": prompt_path.name,
            "generation_tool": "$codex-gpt-image",
            "generation_provider": "codex-oauth",
            "model": str(args.model),
            "generation_mode": "model-native-title",
            "post_generated_text_edit": False,
            "visible_text": [title],
            "title": title,
            "text_policy": "title-only",
            "cover_author_attribution": "forbidden",
            "author_attribution_present": False,
            "width": width,
            "height": height,
            "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
            "prompt_sha256": sha256_text(prompt),
            "metadata_chunks": [],
        }
        atomic_write_json(output, payload)
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, "output": str(output), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
