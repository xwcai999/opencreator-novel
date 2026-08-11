#!/usr/bin/env python3
"""Enforce the title-only cover policy with manifest, prompt, OCR and manual gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from studio_common import atomic_write_json, ensure_within, parse_document, read_text, sha256_text, validate_book_title


FORBIDDEN_FILENAME_MARKERS = ("作者", "笔名", "署名", "author", "byline", "pen-name", "penname")
NATIVE_TITLE_MARKERS = ("一次生成", "直接生成完整封面", "model-native", "in-image title")
TITLE_ONLY_MARKERS = ("只允许", "不得出现任何其他文字", "only visible text", "no other visible text")
NO_ATTRIBUTION_MARKERS = ("无署名", "无作者名", "无笔名", "无签名", "no author", "no signature", "without attribution")
NO_WATERMARK_MARKERS = ("无水印", "no watermark", "without watermark")


def _normalize_visible(value: str) -> str:
    return re.sub(r"[\s\u3000，,。.!！?？:：;；·•—_\-]+", "", value).casefold()


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def validate(args: argparse.Namespace) -> dict[str, object]:
    project_root = Path(args.project_root).expanduser().resolve()
    project_meta, _ = parse_document(project_root / "作品.md")
    title = validate_book_title(str(project_meta.get("title") or ""))
    cover_root = (project_root / "封面").resolve()
    image = Path(args.image).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else image.with_suffix(".manifest.json")
    prompt_path = Path(args.prompt_file).expanduser().resolve()
    ensure_within(cover_root, image)
    ensure_within(cover_root, manifest_path)
    ensure_within(cover_root, prompt_path)
    errors: list[str] = []
    warnings: list[str] = []

    if not image.is_file():
        errors.append(f"封面文件不存在: {image}")
    if not manifest_path.is_file():
        errors.append(f"封面清单不存在: {manifest_path}")
        manifest: dict[str, object] = {}
    else:
        try:
            manifest = json.loads(read_text(manifest_path))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"封面清单无法读取: {exc}")
            manifest = {}
    if not prompt_path.is_file():
        errors.append(f"底图提示词不存在: {prompt_path}")
        prompt = ""
    else:
        prompt = read_text(prompt_path)

    if manifest.get("text_policy") != "title-only":
        errors.append("封面清单的 text_policy 必须为 title-only")
    if manifest.get("schema_version") != 2 or manifest.get("type") != "cover-manifest":
        errors.append("封面清单必须使用 schema-version 2 的 cover-manifest")
    if manifest.get("generation_tool") != "$codex-gpt-image":
        errors.append("封面清单必须声明由 $codex-gpt-image 生成")
    if manifest.get("generation_mode") != "model-native-title":
        errors.append("封面必须由图片模型一次生成画面与书名，拒绝无字底图或后期叠字")
    if manifest.get("post_generated_text_edit") is not False:
        errors.append("封面清单必须明确确认未进行生成后的文字编辑")
    if "source_artwork" in manifest:
        errors.append("封面清单含 source_artwork，疑似使用无字底图加后期叠字")
    if manifest.get("visible_text") != [title]:
        errors.append("封面清单 visible_text 必须且只能包含书名")
    if manifest.get("title") != title:
        errors.append("封面清单书名与校验参数不一致")
    if manifest.get("cover_author_attribution") != "forbidden":
        errors.append("封面清单未声明禁止作者署名")
    if manifest.get("author_attribution_present") is not False:
        errors.append("封面清单未明确确认作者署名不存在")
    forbidden_keys = {"author", "pen_name", "pen-name", "byline", "署名", "笔名"}
    if forbidden_keys.intersection(str(key).casefold() for key in manifest):
        errors.append("封面清单包含作者或笔名字段")
    lowered_name = image.name.casefold()
    if any(marker.casefold() in lowered_name for marker in FORBIDDEN_FILENAME_MARKERS):
        errors.append("封面文件名含作者/笔名/署名标记")

    if image.is_file():
        actual_image_hash = hashlib.sha256(image.read_bytes()).hexdigest()
        if manifest.get("image") != image.name:
            errors.append("封面清单 image 与待校验文件名不一致")
        if manifest.get("image_sha256") != actual_image_hash:
            errors.append("封面图片哈希与清单不一致，可能在生成后被修改")
        if manifest.get("metadata_chunks") != []:
            errors.append("封面清单未确认 PNG 不含文本或 EXIF 元数据块")

    if title not in prompt:
        errors.append("封面提示词必须逐字包含 作品.md 中的规范书名")
    if not _contains_any(prompt, NATIVE_TITLE_MARKERS):
        errors.append("封面提示词必须明确要求书名与画面一次生成")
    if not _contains_any(prompt, TITLE_ONLY_MARKERS):
        errors.append("封面提示词必须明确只允许规范书名作为可见文字")
    if not _contains_any(prompt, NO_ATTRIBUTION_MARKERS):
        errors.append("封面提示词必须明确禁止作者名、笔名或署名")
    if not _contains_any(prompt, NO_WATERMARK_MARKERS):
        errors.append("封面提示词必须明确禁止水印")
    if prompt and manifest.get("prompt") != prompt_path.name:
        errors.append("封面清单 prompt 与待校验提示词文件名不一致")
    if prompt and manifest.get("prompt_sha256") != sha256_text(prompt):
        errors.append("封面提示词哈希与清单不一致")

    ocr_text = ""
    if args.ocr_text is not None:
        ocr_text = args.ocr_text
    elif args.ocr_file:
        ocr_text = read_text(Path(args.ocr_file).expanduser().resolve())
    if ocr_text:
        if _normalize_visible(ocr_text) != _normalize_visible(title):
            errors.append("OCR 结果包含书名以外的可见文字，疑似署名或生成伪文字")
    else:
        warnings.append("当前未提供 OCR 结果；仅可依赖人工逐字复核")

    if not args.manual_review_passed:
        errors.append("必须完成人工视觉复核，并显式传入 --manual-review-passed")

    return {
        "ok": not errors,
        "image": str(image),
        "manifest": str(manifest_path),
        "generation_mode": manifest.get("generation_mode"),
        "allowed_visible_text": [title],
        "ocr_checked": bool(ocr_text),
        "manual_review_passed": bool(args.manual_review_passed),
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验封面只含作品.md中的书名，严禁作者、笔名或任何署名")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--manifest", help="默认取封面同名 .manifest.json")
    ocr = parser.add_mutually_exclusive_group()
    ocr.add_argument("--ocr-text")
    ocr.add_argument("--ocr-file")
    parser.add_argument("--manual-review-passed", action="store_true")
    parser.add_argument("--output", help="可选 JSON 校验报告")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    try:
        result = validate(args)
        if args.output:
            output = ensure_within(project_root / "报告" / "封面", Path(args.output).expanduser().resolve())
            if output.suffix.lower() != ".json":
                raise ValueError("封面校验报告必须是 报告/封面/ 内的 .json 文件")
            atomic_write_json(output, result)
    except (OSError, UnicodeError, ValueError) as exc:
        result = {"ok": False, "errors": [str(exc)], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
