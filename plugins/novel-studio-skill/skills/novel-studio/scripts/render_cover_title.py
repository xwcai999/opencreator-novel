#!/usr/bin/env python3
"""Legacy compatibility: render the book title over no-text cover artwork.

New covers must not use this script. Its manifests are rejected by the current gate.
The CLI intentionally has no author, pen-name, byline, or free-text option.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:  # pragma: no cover - 由 CLI 给出可操作错误
    Image = ImageDraw = ImageFont = None

from studio_common import atomic_write_json, ensure_within, parse_document, validate_book_title


FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/simsun.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
)


def _font_path(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"字体文件不存在: {path}")
        return path
    for path in FONT_CANDIDATES:
        if path.is_file():
            return path
    raise ValueError("未找到可用中文字体，请通过 --font 指定字体文件")


def _lines(title: str, max_lines: int = 3) -> list[str]:
    compact = " ".join(title.split())
    if not compact:
        raise ValueError("书名不能为空")
    if len(compact) <= 10:
        return [compact]
    width = math.ceil(len(compact) / max_lines)
    return [compact[index : index + width] for index in range(0, len(compact), width)]


def _fit_font(draw: ImageDraw.ImageDraw, lines: list[str], font_path: Path, width: int, height: int) -> ImageFont.FreeTypeFont:
    max_width = int(width * 0.78)
    max_height = int(height * 0.34)
    low, high = 18, max(19, int(min(width, height) * 0.16))
    best = ImageFont.truetype(str(font_path), low)
    while low <= high:
        size = (low + high) // 2
        candidate = ImageFont.truetype(str(font_path), size)
        boxes = [draw.textbbox((0, 0), line, font=candidate, stroke_width=max(1, size // 28)) for line in lines]
        block_width = max(box[2] - box[0] for box in boxes)
        line_height = max(box[3] - box[1] for box in boxes)
        block_height = line_height * len(lines) + int(size * 0.28) * (len(lines) - 1)
        if block_width <= max_width and block_height <= max_height:
            best = candidate
            low = size + 1
        else:
            high = size - 1
    return best


def render(project_root: Path, artwork: Path, output: Path, font_arg: str | None) -> dict[str, object]:
    if Image is None or ImageDraw is None or ImageFont is None:
        raise ValueError("缺少 Pillow，无法本地排版封面书名；请先在受控环境安装 Pillow")
    project_root = project_root.expanduser().resolve()
    project_meta, _ = parse_document(project_root / "作品.md")
    title = validate_book_title(str(project_meta.get("title") or ""))
    cover_root = (project_root / "封面").resolve()
    artwork = artwork.expanduser().resolve()
    output = output.expanduser().resolve()
    ensure_within(cover_root, artwork)
    ensure_within(cover_root, output)
    if not artwork.is_file():
        raise ValueError(f"底图不存在: {artwork}")
    ensure_within(artwork.parent, output)
    if artwork == output:
        raise ValueError("输出路径不能覆盖底图")
    if output.suffix.lower() != ".png":
        raise ValueError("输出必须为 PNG，以便剥离来源元数据")

    font_path = _font_path(font_arg)
    lines = _lines(title)
    with Image.open(artwork) as source:
        source.load()
        canvas = Image.new("RGB", source.size)
        canvas.paste(source.convert("RGB"))

    width, height = canvas.size
    if width < 600 or height < 900:
        raise ValueError("封面底图至少需要 600×900 像素")
    draw = ImageDraw.Draw(canvas, "RGBA")
    font = _fit_font(draw, lines, font_path, width, height)
    stroke = max(2, font.size // 26)
    gap = int(font.size * 0.28)
    boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=stroke) for line in lines]
    heights = [box[3] - box[1] for box in boxes]
    total_height = sum(heights) + gap * (len(lines) - 1)
    top = int(height * 0.13)
    padding_x = int(width * 0.08)
    padding_y = int(font.size * 0.55)
    draw.rounded_rectangle(
        (padding_x, top - padding_y, width - padding_x, top + total_height + padding_y),
        radius=max(12, int(font.size * 0.32)),
        fill=(0, 0, 0, 108),
    )
    y = top
    for line, box, line_height in zip(lines, boxes, heights):
        line_width = box[2] - box[0]
        x = (width - line_width) // 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(250, 247, 238, 255),
            stroke_width=stroke,
            stroke_fill=(15, 15, 18, 235),
        )
        y += line_height + gap

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".png", dir=output.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        canvas.save(temp_path, format="PNG", optimize=True)
        temp_path.replace(output)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    manifest = output.with_suffix(".manifest.json")
    payload: dict[str, object] = {
        "schema_version": 1,
        "type": "cover-manifest",
        "image": output.name,
        "source_artwork": artwork.name,
        "generation_mode": "deterministic-overlay",
        "post_generated_text_edit": True,
        "visible_text": [title],
        "title": title,
        "cover_author_attribution": "forbidden",
        "author_attribution_present": False,
        "metadata_stripped": True,
        "text_policy": "title-only",
    }
    atomic_write_json(manifest, payload)
    return {"ok": True, "output": str(output), "manifest": str(manifest), **payload}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="旧项目兼容：在无字底图上叠加书名；新封面工作流会拒绝该产物")
    parser.add_argument("--project-root", required=True, help="从 作品.md 读取唯一允许的书名")
    parser.add_argument("--artwork", required=True, help="由 codex-gpt-image 生成的无字底图")
    parser.add_argument("--output", required=True, help="输出 PNG")
    parser.add_argument("--font", help="可选字体路径")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = render(Path(args.project_root), Path(args.artwork), Path(args.output), args.font)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
