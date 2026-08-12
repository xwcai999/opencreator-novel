#!/usr/bin/env python3
"""蛙蛙投稿材料离线预检。

本模块只负责材料层校验：元数据、封面、正文来源和平台表单字数门槛。
它不登录、不上传，也不替代 ``novel-studio`` 的项目连续性/审稿校验。

安全约定：相对文件路径以 ``base_dir`` 为边界；解析后的真实路径必须仍在
边界内，因而 ``..`` 和指向边界外的符号链接都会失败。输出中的路径默认
只使用相对路径/文件名，避免把本机目录写入报告。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PUBLIC_SIGNING_GUIDANCE = 100_000
HISTORICAL_ONGOING_OBSERVATION = 20_000
HISTORICAL_COMPLETED_OBSERVATION = 30_000
MAX_TITLE_LENGTH = 200
MAX_PEN_NAME_LENGTH = 40
MAX_SUMMARY_LENGTH = 500
MAX_CUSTOM_TAG_LENGTH = 10
COVER_MAX_BYTES = 5 * 1024 * 1024
MANUSCRIPT_MAX_BYTES = 50 * 1024 * 1024
ALLOWED_CHANNELS = {"男频", "女频", "全频"}
ALLOWED_STATUSES = {"连载", "完结"}
ALLOWED_MANUSCRIPT_EXTENSIONS = {".doc", ".docx", ".txt"}
ALLOWED_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
RULE_CACHE = {
    "public_signing_guidance": {
        "checked_at": "2026-08-12",
        "source": "https://wawawriter.com/app/submission",
        "confidence": "high",
        "stale_after": "2026-08-19",
    },
    "historical_form_observation": {
        "checked_at": "2026-08-12",
        "source": "historical local page observation; not a current signing rule",
        "confidence": "medium",
        "stale_after": "2026-08-19",
    },
    "field_and_file_snapshot": {
        "checked_at": "2026-08-11",
        "source": "https://wawawriter.com/app/submission/create",
        "confidence": "medium",
        "stale_after": "2026-08-18",
    },
}


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "name", "book_title", "bookTitle", "作品名", "书名", "作品名称"),
    "pen_name": ("pen_name", "penName", "pen-name", "author", "author_name", "authorName", "nickname", "笔名", "作者笔名"),
    "summary": ("summary", "synopsis", "description", "简介", "内容简介", "作品简介"),
    "channel": ("channel", "频道"),
    "status": ("status", "publication_status", "publicationStatus", "作品状态", "状态"),
    "categories": ("categories", "category", "genre", "category_path", "categoryPath", "三级类目", "三级分类", "分类", "分类目录"),
    "tags": ("tags", "tag", "标签", "关键词"),
    "custom_tags": ("custom_tags", "customTags", "custom-tags", "自定义标签", "自定义tag"),
    "cover": ("cover", "cover_path", "coverPath", "封面", "封面图片", "cover_file"),
    "manuscript": ("manuscript", "submission", "submission_file", "submissionFile", "file", "投稿文件", "投稿稿件", "稿件"),
    "word_count": ("word_count", "wordCount", "words", "字数", "字数统计", "总字数"),
    "history_achievement_images": ("history_achievement_images", "historyAchievementImages", "history_images", "历史成绩证明", "历史成绩图片"),
}
_NESTED_METADATA_KEYS = ("metadata", "meta", "book", "作品", "投稿", "submission")
_STATUS_ALIASES = {
    "ongoing": "连载", "serializing": "连载", "serial": "连载", "连载中": "连载", "连载": "连载",
    "completed": "完结", "complete": "完结", "finished": "完结", "finish": "完结", "已完结": "完结", "完结": "完结",
}
_CHANNEL_ALIASES = {"male": "男频", "female": "女频", "all": "全频"}


class PathSafetyError(ValueError):
    """路径无法在声明的边界内安全解析。"""


def _clean_text(value: Any) -> str:
    return "" if value is None else (value.strip() if isinstance(value, str) else str(value).strip())


def _lookup(data: Mapping[str, Any], aliases: Iterable[str]) -> Any:
    for key in aliases:
        if key in data:
            return data[key]
    for nested_key in _NESTED_METADATA_KEYS:
        nested = data.get(nested_key)
        if isinstance(nested, Mapping):
            for key in aliases:
                if key in nested:
                    return nested[key]
    return None


def _as_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        result = []
        for key in ("level1", "level2", "level3", "一级", "二级", "三级", "一级类目", "二级类目", "三级类目"):
            item = _clean_text(value.get(key))
            if item:
                result.append(item)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(value)
    return [part.strip() for part in re.split(r"[,，;；/、|>＞\\]", text) if part.strip()] if text else []


def _normalise_channel(value: Any) -> str:
    text = _clean_text(value)
    return _CHANNEL_ALIASES.get(text.lower(), text)


def _normalise_status(value: Any) -> str:
    text = _clean_text(value)
    return _STATUS_ALIASES.get(text.lower(), text)


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _count_text_units(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def _rule_cache_status(today: dt.date | None = None) -> dict[str, dict[str, Any]]:
    current = today or dt.date.today()
    result: dict[str, dict[str, Any]] = {}
    for name, record in RULE_CACHE.items():
        item = dict(record)
        item["stale"] = current > dt.date.fromisoformat(item["stale_after"])
        item["verification_status"] = "未实时复核" if item["stale"] else "缓存期内，提交前仍需实时复核"
        result[name] = item
    return result


def _within(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _display_path(path: Path | None, root: Path | None = None) -> str | None:
    """返回不泄漏本机根目录的相对路径。"""

    if path is None:
        return None
    if root is not None:
        try:
            relative = path.relative_to(root)
            return relative.as_posix() or "."
        except ValueError:
            return f"<outside>/{path.name}"
    return path.name or "."


def _resolve_path(value: Any, base_dir: Path | None) -> Path | None:
    if isinstance(value, Mapping):
        for key in ("path", "file", "filename", "file_path", "filePath", "地址", "路径"):
            if key in value:
                value = value[key]
                break
    text = _clean_text(value)
    if not text:
        return None
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = (base_dir if base_dir is not None else Path.cwd()) / candidate
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise PathSafetyError("路径无法解析") from exc
    if base_dir is not None:
        boundary = base_dir.expanduser().resolve(strict=False)
        if not _within(boundary, resolved):
            raise PathSafetyError("路径越界")
    return resolved


def _declared_size(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("size_bytes", "sizeBytes", "bytes", "size", "文件大小"):
        if key in value:
            return _int_value(value[key])
    return None


def _file_size(path: Path | None) -> int | None:
    try:
        return path.stat().st_size if path is not None and path.is_file() else None
    except OSError:
        return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _valid_png(data: bytes) -> bool:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset, saw_ihdr, saw_iend = 8, False, False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            return False
        chunk = data[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        if (zlib_crc := __import__("zlib").crc32(kind + chunk) & 0xFFFFFFFF) != crc:
            return False
        if not saw_ihdr:
            if kind != b"IHDR" or length != 13:
                return False
            width, height = struct.unpack(">II", chunk[:8])
            if width <= 0 or height <= 0:
                return False
            saw_ihdr = True
        if kind == b"IEND":
            saw_iend = True
            return saw_ihdr and length == 0 and end == len(data)
        offset = end
    return False


def _valid_jpeg(data: bytes) -> bool:
    if len(data) < 4 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        return False
    i, saw_frame = 2, False
    frame_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
    while i < len(data) - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > len(data):
            return False
        length = struct.unpack(">H", data[i : i + 2])[0]
        if length < 2 or i + length > len(data):
            return False
        if marker in frame_markers and length >= 7:
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            if width <= 0 or height <= 0:
                return False
            saw_frame = True
        i += length
        if marker == 0xDA:
            break
    return saw_frame


def _valid_webp(data: bytes) -> bool:
    if len(data) < 16 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False
    declared = struct.unpack("<I", data[4:8])[0]
    return declared + 8 <= len(data) and data[12:16] in {b"VP8 ", b"VP8L", b"VP8X"}


def _validate_image_bytes(path: Path, extension: str) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return f"无法读取图片: {exc.__class__.__name__}"
    if extension in {".jpg", ".jpeg"} and not _valid_jpeg(data):
        return "JPEG 文件结构无效"
    if extension == ".png" and not _valid_png(data):
        return "PNG 文件结构无效"
    if extension == ".webp" and not _valid_webp(data):
        return "WEBP 文件结构无效"
    return None


def _validate_cover(value: Any, base_dir: Path | None, errors: list[str], info: dict[str, Any], *, label: str = "封面") -> None:
    if value in (None, ""):
        return
    try:
        path = _resolve_path(value, base_dir)
    except PathSafetyError as exc:
        errors.append(f"{label}路径{exc}")
        return
    extension = path.suffix.lower() if path else ""
    info.update({"path": _display_path(path, base_dir), "extension": extension})
    if extension not in ALLOWED_COVER_EXTENSIONS:
        errors.append(f"{label}格式不支持: {extension or '未知'}，仅支持 " + ", ".join(sorted(ALLOWED_COVER_EXTENSIONS)))
    size = _file_size(path)
    if size is None:
        size = _declared_size(value)
    if path is None or not path.is_file():
        errors.append(f"{label}文件不存在: {_display_path(path, base_dir) or '<unknown>'}")
    elif extension in ALLOWED_COVER_EXTENSIONS:
        reason = _validate_image_bytes(path, extension)
        if reason:
            errors.append(f"{label}文件内容无效: {reason}")
    if size is not None:
        info["size_bytes"] = size
        if size < 0:
            errors.append(f"{label}文件大小不能为负数")
        elif size > COVER_MAX_BYTES:
            errors.append(f"{label}文件过大: {size} 字节，限制为 5MB")


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {"[Content_Types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise ValueError("DOCX 缺少必要的 OOXML 部件")
            if any(info.flag_bits & 0x1 for info in archive.infolist()):
                raise ValueError("DOCX 含加密部件，无法离线解析")
            root = ET.fromstring(archive.read("word/document.xml"))
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("DOCX 不是可解析的 OOXML 文档") from exc
    return "".join(element.text or "" for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "t")


def _validate_manuscript(value: Any, base_dir: Path | None, errors: list[str], blockers: list[str], info: dict[str, Any], *, source_label: str = "投稿文件") -> str | None:
    if value in (None, ""):
        return None
    try:
        path = _resolve_path(value, base_dir)
    except PathSafetyError as exc:
        errors.append(f"{source_label}路径{exc}")
        return None
    if path is None:
        errors.append(f"{source_label}路径为空")
        return None
    extension = path.suffix.lower()
    info.update({"path": _display_path(path, base_dir), "extension": extension})
    if extension not in ALLOWED_MANUSCRIPT_EXTENSIONS:
        errors.append(f"{source_label}扩展名不支持: {extension or '无'}，仅支持 " + ", ".join(sorted(ALLOWED_MANUSCRIPT_EXTENSIONS)))
    size = _file_size(path)
    if size is None:
        size = _declared_size(value)
    if not path.is_file():
        errors.append(f"{source_label}文件不存在: {_display_path(path, base_dir)}")
        return None
    if size is not None:
        info["size_bytes"] = size
        if size < 0:
            errors.append(f"{source_label}文件大小不能为负数")
        elif size > MANUSCRIPT_MAX_BYTES:
            errors.append(f"{source_label}文件过大: {size} 字节，限制为 50MB")
    if extension == ".txt":
        try:
            info["parse_status"] = "parsed"
            return _read_text(path)
        except OSError as exc:
            errors.append(f"无法读取{source_label}: {exc.__class__.__name__}")
            return None
    if extension == ".docx":
        try:
            text = _extract_docx_text(path)
            info["parse_status"] = "parsed"
            return text
        except ValueError as exc:
            info["parse_status"] = "invalid"
            errors.append(f"{source_label} DOCX 解析失败: {exc}")
            return None
    if extension == ".doc":
        # 标准库无法可靠解析旧式 OLE Compound Document；拒绝以声明字数冒充实测。
        info["parse_status"] = "unsupported"
        blockers.append(f"{source_label}为旧式 DOC，当前离线预检无法可靠解析；请转换为真实 DOCX 或 TXT")
    return None


def _safe_project_file(path: Path, root: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    return resolved if _within(root, resolved) else None


def validate_project_adapter(project_root: str | Path) -> dict[str, Any]:
    """读取项目投稿相关材料，并拒绝正文/报告符号链接越界。"""

    try:
        root = Path(project_root).expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return {"path": ".", "ok": False, "errors": ["项目目录路径无法解析"], "warnings": [], "read_files": [], "report_files": [], "word_count": None}
    result: dict[str, Any] = {"path": ".", "ok": True, "errors": [], "warnings": [], "read_files": [], "report_files": [], "word_count": None}
    errors: list[str] = result["errors"]
    warnings: list[str] = result["warnings"]
    if not root.is_dir():
        errors.append("项目目录不存在")
        result["ok"] = False
        return result

    project_file = _safe_project_file(root / "作品.md", root)
    if project_file is not None and project_file.is_file():
        try:
            _read_text(project_file)
            result["read_files"].append("作品.md")
        except OSError as exc:
            errors.append(f"无法读取作品.md: {exc.__class__.__name__}")
    else:
        warnings.append("项目缺少作品.md，无法读取项目元信息")

    body_root = root / "正文"
    if not body_root.is_dir():
        warnings.append("项目缺少正文目录，无法从项目统计字数")
    else:
        text_files: list[Path] = []
        for current, dirs, files in os.walk(body_root, followlinks=False):
            current_path = Path(current)
            for directory in list(dirs):
                candidate = current_path / directory
                if candidate.is_symlink():
                    if _safe_project_file(candidate, root) is None:
                        errors.append(f"正文路径越界: {_display_path(candidate, root)}")
                    dirs.remove(directory)
            for filename in files:
                candidate = current_path / filename
                safe = _safe_project_file(candidate, root)
                if safe is None:
                    errors.append(f"正文路径越界: {_display_path(candidate, root)}")
                    continue
                if safe.suffix.lower() in {".md", ".markdown", ".txt"} and safe.is_file():
                    text_files.append(safe)
        total, readable = 0, 0
        for path in sorted(set(text_files)):
            try:
                total += _count_text_units(_read_text(path))
                readable += 1
                result["read_files"].append(path.relative_to(root).as_posix())
            except OSError as exc:
                errors.append(f"无法读取正文文件 {path.relative_to(root).as_posix()}: {exc.__class__.__name__}")
        if readable:
            result["word_count"] = total
        elif not text_files:
            warnings.append("正文目录中没有可读取的 Markdown/TXT 文件")

    report_root = root / "报告"
    if report_root.is_dir():
        for current, dirs, files in os.walk(report_root, followlinks=False):
            current_path = Path(current)
            for directory in list(dirs):
                candidate = current_path / directory
                if candidate.is_symlink():
                    if _safe_project_file(candidate, root) is None:
                        errors.append(f"报告路径越界: {_display_path(candidate, root)}")
                    dirs.remove(directory)
            for filename in files:
                candidate = current_path / filename
                safe = _safe_project_file(candidate, root)
                if safe is None:
                    errors.append(f"报告路径越界: {_display_path(candidate, root)}")
                    continue
                result["report_files"].append(safe.relative_to(root).as_posix())
    result["ok"] = not errors
    return result


def _normalise_categories(data: Mapping[str, Any]) -> list[str]:
    items = _as_items(_lookup(data, FIELD_ALIASES["categories"]))
    if items:
        return items
    result: list[str] = []
    for aliases in (("category_level_1", "categoryLevel1", "一级类目"), ("category_level_2", "categoryLevel2", "二级类目"), ("category_level_3", "categoryLevel3", "三级类目")):
        item = _clean_text(_lookup(data, aliases))
        if item:
            result.append(item)
    return result


def _validate_history_images(value: Any, base_dir: Path | None, errors: list[str]) -> list[dict[str, Any]]:
    if value in (None, "", []):
        return []
    items = list(value) if isinstance(value, (list, tuple)) else [value]
    if not 1 <= len(items) <= 10:
        errors.append("历史成绩证明须为 1—10 张图片")
    results: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        info: dict[str, Any] = {"index": index}
        before = len(errors)
        _validate_cover(item, base_dir, errors, info, label="历史成绩证明")
        if len(errors) > before:
            errors[before:] = [f"历史成绩证明第 {index} 张：{message}" for message in errors[before:]]
        results.append(info)
    return results


def validate_submission(metadata: Mapping[str, Any], *, manuscript: str | Path | Mapping[str, Any] | None = None, project_root: str | Path | None = None, base_dir: str | Path | None = None) -> dict[str, Any]:
    """校验独立稿件或 Novel Studio 集成项目。"""

    if not isinstance(metadata, Mapping):
        return {"ok": False, "errors": ["元数据 JSON 须为对象"], "blockers": [], "warnings": [], "mode": "independent"}
    errors: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    root = Path(base_dir).expanduser().resolve(strict=False) if base_dir else None
    mode = "integrated" if project_root is not None else "independent"
    rules = _rule_cache_status()
    if mode == "independent":
        warnings.append("独立模式仅完成本地材料预检，不代表平台接受、签约或提交成功")

    title = _clean_text(_lookup(metadata, FIELD_ALIASES["title"]))
    pen_name = _clean_text(_lookup(metadata, FIELD_ALIASES["pen_name"]))
    summary = _clean_text(_lookup(metadata, FIELD_ALIASES["summary"]))
    channel = _normalise_channel(_lookup(metadata, FIELD_ALIASES["channel"]))
    status = _normalise_status(_lookup(metadata, FIELD_ALIASES["status"]))
    categories = _normalise_categories(metadata)
    tags = _as_items(_lookup(metadata, FIELD_ALIASES["tags"]))
    custom_tags = _as_items(_lookup(metadata, FIELD_ALIASES["custom_tags"]))
    if not title: blockers.append("作品名称不能为空")
    elif len(title) > MAX_TITLE_LENGTH: errors.append(f"作品名称长度不能超过 {MAX_TITLE_LENGTH} 字符")
    if not pen_name: blockers.append("笔名不能为空")
    elif len(pen_name) > MAX_PEN_NAME_LENGTH: errors.append(f"笔名长度不能超过 {MAX_PEN_NAME_LENGTH} 字符")
    if not summary or summary == "暂无简介": blockers.append("作品简介必须填写正式内容，不能留空或使用“暂无简介”占位")
    elif len(summary) > MAX_SUMMARY_LENGTH: errors.append(f"简介长度不能超过 {MAX_SUMMARY_LENGTH} 字符")
    if not channel: blockers.append("频道尚未确认，须选择男频、女频或全频")
    elif channel not in ALLOWED_CHANNELS: errors.append(f"频道必须为男频、女频或全频，当前为 {channel}")
    if not status: blockers.append("作品状态尚未确认，须按事实选择连载或完结")
    elif status not in ALLOWED_STATUSES: errors.append(f"状态必须为连载或完结，当前为 {status}")
    if not categories: blockers.append("后台三级类目尚未确认，须从当前页面选择 3 项")
    elif len(categories) != 3: errors.append(f"三级类目必须恰好填写 3 项，当前为 {len(categories)} 项")
    if not tags: blockers.append("至少填写 1 个标签")
    for tag in custom_tags:
        if len(tag) > MAX_CUSTOM_TAG_LENGTH: errors.append(f"自定义标签“{tag}”长度不能超过 {MAX_CUSTOM_TAG_LENGTH} 字符")

    cover_info: dict[str, Any] = {}
    cover_value = _lookup(metadata, FIELD_ALIASES["cover"])
    if cover_value in (None, ""): blockers.append("缺少作品封面")
    else: _validate_cover(cover_value, root, errors, cover_info)
    history_images = _validate_history_images(_lookup(metadata, FIELD_ALIASES["history_achievement_images"]), root, errors)

    manuscript_info: dict[str, Any] = {}
    manuscript_value = manuscript if manuscript is not None else _lookup(metadata, FIELD_ALIASES["manuscript"])
    has_manuscript = manuscript_value not in (None, "")
    if not has_manuscript and project_root is None:
        blockers.append("缺少正文来源：须提供投稿文件或 Novel Studio 项目目录")
    manuscript_text = _validate_manuscript(manuscript_value, root, errors, blockers, manuscript_info) if has_manuscript else None

    project_info: dict[str, Any] | None = None
    project_text_count: int | None = None
    if project_root is not None:
        project_info = validate_project_adapter(project_root)
        errors.extend(project_info["errors"])
        warnings.extend(project_info["warnings"])
        project_text_count = project_info.get("word_count")
        if project_text_count is None and not has_manuscript:
            blockers.append("项目正文为空或无法读取，不能仅凭元数据声明字数通过预检")

    word_count: int | None = None
    word_source = ""
    if manuscript_text is not None:
        word_count, word_source = _count_text_units(manuscript_text), "manuscript"
    elif project_text_count is not None:
        word_count, word_source = int(project_text_count), "project"
    elif project_root is None and not has_manuscript:
        declared = _lookup(metadata, FIELD_ALIASES["word_count"])
        if declared not in (None, ""):
            errors.append("未提供可验证正文，不能使用声明字数替代稿件")
    if word_count is not None:
        if word_source in {"manuscript", "project"}:
            warnings.append("本地字数仅为预检估算，最终以蛙蛙页面解析字数为准")
        public_rule = rules["public_signing_guidance"]
        historical_rule = rules["historical_form_observation"]
        if word_count < PUBLIC_SIGNING_GUIDANCE:
            warnings.append(
                f"当前公开投稿页提示长篇约 10 万字方可正式签约；当前本地估算约 {word_count} 字。"
                f"该提示不是签约保证；规则状态：{public_rule['verification_status']}。"
            )
        historical_threshold = (
            HISTORICAL_ONGOING_OBSERVATION if status == "连载" else HISTORICAL_COMPLETED_OBSERVATION
        )
        if status in ALLOWED_STATUSES and word_count < historical_threshold:
            warnings.append(
                f"历史页面快照曾观察到{status}作品约 {historical_threshold} 字的状态校验；"
                f"规则状态：{historical_rule['verification_status']}，不能作为当前阻断或平台保证。"
            )
    elif status in ALLOWED_STATUSES and not any("无法可靠解析" in item for item in blockers):
        blockers.append("未提供可计算的稿件字数，无法完成材料预检")

    result: dict[str, Any] = {
        "ok": not errors and not blockers,
        "mode": mode,
        "errors": errors,
        "blockers": blockers,
        "warnings": warnings,
        "metadata": {"title": title, "pen_name": pen_name, "summary": summary, "channel": channel, "status": status, "categories": categories, "tags": tags, "custom_tags": custom_tags},
        "cover": cover_info,
        "history_achievement_images": history_images,
        "manuscript": manuscript_info,
        "word_count": word_count,
        "word_count_source": word_source or None,
        "rules": rules,
        "page_verification": {
            "verified_at": None,
            "page_status": "未实时复核",
            "parsed_word_count": None,
            "actual_message": None,
        },
    }
    if project_info is not None: result["project"] = project_info
    return result


def _load_metadata(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping): raise ValueError("元数据 JSON 须为对象")
    return value


def _human_output(result: Mapping[str, Any]) -> str:
    lines = ["结果: 通过" if result.get("ok") else "结果: 未通过"]
    for label, heading in (("errors", "错误:"), ("blockers", "阻断:"), ("warnings", "警告:")):
        values = result.get(label) or []
        if values: lines.extend([heading, *[f"- {item}" for item in values]])
    if result.get("word_count") is not None: lines.append(f"字数: {result['word_count']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="蛙蛙投稿元数据、稿件及字数门槛预检")
    parser.add_argument("--metadata", required=True, help="投稿元数据 JSON 文件")
    parser.add_argument("--project-root", help="可选 Novel Studio 项目目录")
    parser.add_argument("--manuscript", help="可选投稿稿件（.doc/.docx/.txt）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    metadata_path = Path(args.metadata).expanduser().resolve(strict=False)
    try:
        metadata = _load_metadata(metadata_path)
        result = validate_submission(metadata, manuscript=args.manuscript, project_root=args.project_root, base_dir=metadata_path.parent)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {"ok": False, "mode": "independent", "errors": [f"无法读取元数据: {exc}"], "blockers": [], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else _human_output(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
