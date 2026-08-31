#!/usr/bin/env python3
"""蛙蛙执行就绪投稿包的轻量预检。

本脚本只检查投稿所需的元数据、文件格式/大小和固定分类标签。
字数仅作信息展示，不阻断用户主动触发的页面预填。
传入 Novel Studio 项目目录时，仅适配读取 ``作品.md``、``正文`` 和 ``报告``，
不执行连续性、审稿或封面生成检查。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


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
REFERENCE_ROOT = Path(__file__).resolve().parent.parent / "references"
DEFAULT_CATEGORY_SNAPSHOT = REFERENCE_ROOT / "wawa-categories.json"
DEFAULT_TAG_SNAPSHOT = REFERENCE_ROOT / "wawa-tags.json"


# 允许表单 JSON 使用中文字段或常见英文别名。规范化输出始终使用下面的英文键。
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "name", "book_title", "bookTitle", "作品名", "书名", "作品名称"),
    "pen_name": (
        "pen_name",
        "penName",
        "pen-name",
        "author",
        "author_name",
        "authorName",
        "nickname",
        "笔名",
        "作者笔名",
    ),
    "summary": ("summary", "synopsis", "description", "简介", "内容简介", "作品简介"),
    "channel": ("channel", "频道"),
    "status": ("status", "publication_status", "publicationStatus", "作品状态", "状态"),
    "categories": (
        "categories",
        "category",
        "genre",
        "category_path",
        "categoryPath",
        "三级类目",
        "三级分类",
        "分类",
        "分类目录",
    ),
    "tags": ("tags", "tag", "标签", "关键词"),
    "custom_tags": ("custom_tags", "customTags", "custom-tags", "自定义标签", "自定义tag"),
    "cover": ("cover", "cover_path", "coverPath", "封面", "封面图片", "cover_file"),
    "manuscript": (
        "manuscript",
        "submission",
        "submission_file",
        "submissionFile",
        "file",
        "投稿文件",
        "投稿稿件",
        "稿件",
    ),
    "word_count": (
        "word_count",
        "wordCount",
        "words",
        "字数",
        "字数统计",
        "总字数",
    ),
    "history_achievement_images": (
        "history_achievement_images",
        "historyAchievementImages",
        "history_images",
        "历史成绩证明",
        "历史成绩图片",
    ),
}

_NESTED_METADATA_KEYS = ("metadata", "meta", "book", "作品", "投稿", "submission")
_STATUS_ALIASES = {
    "ongoing": "连载",
    "serializing": "连载",
    "serial": "连载",
    "连载中": "连载",
    "连载": "连载",
    "completed": "完结",
    "complete": "完结",
    "finished": "完结",
    "finish": "完结",
    "已完结": "完结",
    "完结": "完结",
}
_CHANNEL_ALIASES = {"male": "男频", "female": "女频", "all": "全频"}


def _clean_text(value: Any) -> str:
    """将表单值转为去首尾空白的文本；None 视为空。"""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _lookup(data: Mapping[str, Any], aliases: Iterable[str]) -> Any:
    """从顶层及少量常见嵌套对象中读取一个字段。"""

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
    """把数组或常见分隔符文本转成非空项目列表。"""

    if value is None:
        return []
    if isinstance(value, Mapping):
        # 三级类目常以 level1/level2/level3 或中文键表示。
        ordered = []
        for key in (
            "level1",
            "level2",
            "level3",
            "一级",
            "二级",
            "三级",
            "一级类目",
            "二级类目",
            "三级类目",
        ):
            if key in value:
                item = _clean_text(value[key])
                if item:
                    ordered.append(item)
        return ordered
    if isinstance(value, (list, tuple, set)):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,，;；/、|>＞\\]", text) if part.strip()]


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
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _count_text_units(text: str) -> int:
    """统计去掉空白后的字符数，适合作为中文投稿字数的保守估计。"""

    return sum(1 for char in text if not char.isspace())


def _resolve_path(value: Any, base_dir: Path | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in ("path", "file", "filename", "file_path", "filePath", "地址", "路径"):
            if key in value:
                value = value[key]
                break
    text = _clean_text(value)
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path.resolve()


def _declared_size(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    for key in ("size_bytes", "sizeBytes", "bytes", "size", "文件大小"):
        if key in value:
            return _int_value(value[key])
    return None


def _cover_extension(value: Any, path: Path | None) -> str:
    format_value: Any = None
    if isinstance(value, Mapping):
        for key in ("format", "extension", "ext", "mime", "格式"):
            if key in value:
                format_value = value[key]
                break
    if format_value:
        text = _clean_text(format_value).lower()
        if "/" in text:
            text = text.rsplit("/", 1)[-1]
        if not text.startswith("."):
            text = "." + text
        return text
    return path.suffix.lower() if path else ""


def _file_size(path: Path) -> int | None:
    try:
        if path.is_file():
            return path.stat().st_size
    except OSError:
        return None
    return None


def _read_text(path: Path) -> str:
    # 投稿 TXT/项目文档通常为 UTF-8；替换异常字节以保证预检不中断。
    return path.read_text(encoding="utf-8", errors="replace")


def _validate_cover(value: Any, base_dir: Path | None, errors: list[str], info: dict[str, Any]) -> None:
    if value in (None, ""):
        return
    path = _resolve_path(value, base_dir)
    extension = _cover_extension(value, path)
    info["path"] = str(path) if path else None
    info["extension"] = extension
    if extension not in ALLOWED_COVER_EXTENSIONS:
        errors.append(
            f"封面格式不支持: {extension or '未知'}，仅支持 "
            + ", ".join(sorted(ALLOWED_COVER_EXTENSIONS))
        )
    size = _file_size(path) if path else None
    if size is None:
        size = _declared_size(value)
    if path and not path.is_file():
        errors.append(f"封面文件不存在: {path}")
    if size is not None:
        info["size_bytes"] = size
        if size < 0:
            errors.append("封面文件大小不能为负数")
        elif size > COVER_MAX_BYTES:
            errors.append(f"封面文件过大: {size} 字节，限制为 5MB")


def _validate_history_images(
    value: Any,
    base_dir: Path | None,
    errors: list[str],
) -> list[dict[str, Any]]:
    if value in (None, "", []):
        return []
    items = list(value) if isinstance(value, (list, tuple)) else [value]
    if not 1 <= len(items) <= 10:
        errors.append("历史成绩证明须为 1—10 张图片")
    results: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        info: dict[str, Any] = {"index": index}
        before = len(errors)
        _validate_cover(item, base_dir, errors, info)
        if len(errors) > before:
            errors[before:] = [f"历史成绩证明第 {index} 张：{message}" for message in errors[before:]]
        results.append(info)
    return results


def _validate_manuscript(
    value: Any,
    base_dir: Path | None,
    errors: list[str],
    info: dict[str, Any],
    *,
    source_label: str = "投稿文件",
) -> str | None:
    """检查投稿文件并在可读文本时返回其正文。"""

    if value in (None, ""):
        return None
    path = _resolve_path(value, base_dir)
    if path is None:
        errors.append(f"{source_label}路径为空")
        return None
    extension = path.suffix.lower()
    size = _file_size(path)
    info.update({"path": str(path), "extension": extension})
    if extension not in ALLOWED_MANUSCRIPT_EXTENSIONS:
        errors.append(
            f"{source_label}扩展名不支持: {extension or '无'}，仅支持 "
            + ", ".join(sorted(ALLOWED_MANUSCRIPT_EXTENSIONS))
        )
    if size is None:
        size = _declared_size(value)
    if not path.is_file():
        errors.append(f"{source_label}文件不存在: {path}")
    if size is not None:
        info["size_bytes"] = size
        if size < 0:
            errors.append(f"{source_label}文件大小不能为负数")
        elif size > MANUSCRIPT_MAX_BYTES:
            errors.append(f"{source_label}文件过大: {size} 字节，限制为 50MB")
    if path.is_file() and extension == ".txt":
        try:
            return _read_text(path)
        except OSError as exc:
            errors.append(f"无法读取{source_label}: {exc}")
    return None


def validate_project_adapter(project_root: str | Path) -> dict[str, Any]:
    """读取 Novel Studio 项目的投稿相关材料。

    这是有意保持很窄的适配层：只访问 ``作品.md``、``正文`` 和 ``报告``，
    不检查项目的连续性、章节审稿结果或封面内容。
    """

    root = Path(project_root).expanduser().resolve()
    result: dict[str, Any] = {
        "path": str(root),
        "ok": True,
        "errors": [],
        "warnings": [],
        "read_files": [],
        "report_files": [],
        "word_count": None,
    }
    errors = result["errors"]
    warnings = result["warnings"]
    if not root.is_dir():
        errors.append(f"项目目录不存在: {root}")
        result["ok"] = False
        return result

    project_file = root / "作品.md"
    if project_file.is_file():
        try:
            _read_text(project_file)
            result["read_files"].append("作品.md")
        except OSError as exc:
            errors.append(f"无法读取作品.md: {exc}")
    else:
        warnings.append("项目缺少作品.md，无法读取项目元信息")

    body_root = root / "正文"
    text_files: list[Path] = []
    if not body_root.is_dir():
        warnings.append("项目缺少正文目录，无法从项目统计字数")
    else:
        try:
            for path in sorted(body_root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in {".md", ".markdown", ".txt"}:
                    continue
                text_files.append(path)
        except OSError as exc:
            errors.append(f"无法遍历正文目录: {exc}")
        total = 0
        for path in text_files:
            try:
                text = _read_text(path)
            except OSError as exc:
                errors.append(f"无法读取正文文件 {path.relative_to(root).as_posix()}: {exc}")
                continue
            relative = path.relative_to(root).as_posix()
            result["read_files"].append(relative)
            total += _count_text_units(text)
        if text_files:
            result["word_count"] = total
        else:
            warnings.append("正文目录中没有可读取的 Markdown/TXT 文件")

    report_root = root / "报告"
    if report_root.is_dir():
        try:
            result["report_files"] = [
                path.relative_to(root).as_posix()
                for path in sorted(report_root.rglob("*"))
                if path.is_file()
            ]
        except OSError as exc:
            errors.append(f"无法遍历报告目录: {exc}")

    result["ok"] = not errors
    return result


def _normalise_categories(data: Mapping[str, Any]) -> list[str]:
    value = _lookup(data, FIELD_ALIASES["categories"])
    items = _as_items(value)
    if items:
        return items
    # 兼容表单按三级字段分别提交的情况。
    separate: list[str] = []
    for aliases in (
        ("category_level_1", "categoryLevel1", "一级类目"),
        ("category_level_2", "categoryLevel2", "二级类目"),
        ("category_level_3", "categoryLevel3", "三级类目"),
    ):
        item = _clean_text(_lookup(data, aliases))
        if item:
            separate.append(item)
    return separate


def _normalise_tags(value: Any) -> list[str]:
    return _as_items(value)


def _snapshot_path(value: str | Path | None, default_path: Path) -> Path:
    """解析快照路径；未显式传入时使用 Skill 内置的固定快照。"""

    return Path(value).expanduser().resolve() if value is not None else default_path.resolve()


def _load_snapshot(path: Path, *, label: str) -> tuple[Mapping[str, Any] | None, dict[str, Any], str | None]:
    """读取快照，并把读取状态写入可序列化摘要。"""

    info: dict[str, Any] = {"path": str(path), "loaded": False}
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, info, f"无法读取{label}快照: {exc}"
    if not isinstance(value, Mapping):
        return None, info, f"{label}快照格式无效：根节点须为对象"
    info["loaded"] = True
    info["schema_version"] = value.get("schema_version")
    info["sha256"] = hashlib.sha256(raw).hexdigest()
    return value, info, None


def _snapshot_node_name(node: Any) -> str:
    if not isinstance(node, Mapping):
        return ""
    # 页面展示优先使用 label；缺少 label 时兼容仅存 value 的精简快照。
    return _clean_text(node.get("label") if node.get("label") is not None else node.get("value"))


def _load_category_snapshot(
    value: str | Path | None,
) -> tuple[set[tuple[str, str, str]] | None, dict[str, Any], str | None]:
    path = _snapshot_path(value, DEFAULT_CATEGORY_SNAPSHOT)
    payload, info, error = _load_snapshot(path, label="作品分类")
    if error or payload is None:
        return None, info, error

    roots = payload.get("categories")
    if not isinstance(roots, list):
        return None, info, "作品分类快照格式无效：缺少 categories 数组"

    paths: set[tuple[str, str, str]] = set()
    invalid = False
    for root in roots:
        root_name = _snapshot_node_name(root)
        middle_nodes = root.get("children") if isinstance(root, Mapping) else None
        if not root_name or not isinstance(middle_nodes, list):
            invalid = True
            continue
        for middle in middle_nodes:
            middle_name = _snapshot_node_name(middle)
            leaf_nodes = middle.get("children") if isinstance(middle, Mapping) else None
            if not middle_name or not isinstance(leaf_nodes, list):
                invalid = True
                continue
            for leaf in leaf_nodes:
                leaf_name = _snapshot_node_name(leaf)
                if not leaf_name:
                    invalid = True
                    continue
                category_path = (root_name, middle_name, leaf_name)
                if category_path in paths:
                    return None, info, "作品分类快照格式无效：存在重复完整三级路径"
                paths.add(category_path)

    if invalid or not paths:
        return None, info, "作品分类快照格式无效：须包含完整三级分类树"
    declared_count = payload.get("path_count")
    if declared_count is not None:
        expected_count = _int_value(declared_count)
        if expected_count is None or expected_count != len(paths):
            return None, info, "作品分类快照格式无效：path_count 与实际三级路径数量不一致"
    info["path_count"] = len(paths)
    info["roots"] = sorted({item[0] for item in paths})
    return paths, info, None


def _load_tag_snapshot(value: str | Path | None) -> tuple[set[str] | None, dict[str, Any], str | None]:
    path = _snapshot_path(value, DEFAULT_TAG_SNAPSHOT)
    payload, info, error = _load_snapshot(path, label="作品标签")
    if error or payload is None:
        return None, info, error

    raw_tags = payload.get("tags")
    if not isinstance(raw_tags, list):
        return None, info, "作品标签快照格式无效：缺少 tags 数组"
    normalised_tags = [_clean_text(item) for item in raw_tags if _clean_text(item)]
    tags = set(normalised_tags)
    if not tags:
        return None, info, "作品标签快照格式无效：tags 数组不能为空"
    if len(tags) != len(normalised_tags):
        return None, info, "作品标签快照格式无效：存在重复标签"
    declared_count = payload.get("count")
    if declared_count is not None:
        expected_count = _int_value(declared_count)
        if expected_count is None or expected_count != len(tags):
            return None, info, "作品标签快照格式无效：count 与实际标签数量不一致"
    info["tag_count"] = len(tags)
    return tags, info, None


def validate_submission(
    metadata: Mapping[str, Any],
    *,
    manuscript: str | Path | Mapping[str, Any] | None = None,
    project_root: str | Path | None = None,
    base_dir: str | Path | None = None,
    category_snapshot: str | Path | None = None,
    tag_snapshot: str | Path | None = None,
) -> dict[str, Any]:
    """校验元数据及可选稿件，返回可序列化的结果字典。

    ``manuscript`` 和 ``project_root`` 是 CLI 参数的显式输入；若未提供稿件，
    才会回退到元数据中的投稿文件路径。路径默认相对 ``base_dir`` 解析。分类与
    标签默认使用 Skill 内置固定快照；调用方可通过对应参数显式替换快照。
    """

    errors: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(metadata, Mapping):
        return {
            "ok": False,
            "errors": ["元数据 JSON 须为对象"],
            "blockers": [],
            "warnings": [],
        }
    schema_version = metadata.get("schema_version")
    package_type = _clean_text(metadata.get("type"))
    workflow = metadata.get("workflow")
    campaign = metadata.get("campaign")
    if schema_version is not None:
        if schema_version != 2:
            errors.append("执行就绪投稿包 schema_version 必须为 2")
        if package_type != "wawa-submission-package":
            errors.append("执行就绪投稿包 type 必须为 wawa-submission-package")
        if not isinstance(workflow, Mapping):
            errors.append("执行就绪投稿包缺少 workflow 对象")
        else:
            if _clean_text(workflow.get("mode")) != "page_prefill":
                errors.append("workflow.mode 必须为 page_prefill")
            if _clean_text(workflow.get("final_submit")) != "human_only":
                errors.append("workflow.final_submit 必须为 human_only")
        if not isinstance(campaign, Mapping):
            errors.append("执行就绪投稿包缺少 campaign 对象")
        else:
            if not _clean_text(campaign.get("name")):
                errors.append("campaign.name 不能为空")
            if _clean_text(campaign.get("match_mode")) != "exact":
                errors.append("campaign.match_mode 必须为 exact")
    root = Path(base_dir).expanduser().resolve() if base_dir else None

    title = _clean_text(_lookup(metadata, FIELD_ALIASES["title"]))
    pen_name = _clean_text(_lookup(metadata, FIELD_ALIASES["pen_name"]))
    summary = _clean_text(_lookup(metadata, FIELD_ALIASES["summary"]))
    channel = _normalise_channel(_lookup(metadata, FIELD_ALIASES["channel"]))
    status = _normalise_status(_lookup(metadata, FIELD_ALIASES["status"]))
    categories = _normalise_categories(metadata)
    tags = _normalise_tags(_lookup(metadata, FIELD_ALIASES["tags"]))
    custom_tags = _normalise_tags(_lookup(metadata, FIELD_ALIASES["custom_tags"]))

    category_paths, category_snapshot_info, category_snapshot_error = _load_category_snapshot(
        category_snapshot
    )
    tag_values, tag_snapshot_info, tag_snapshot_error = _load_tag_snapshot(tag_snapshot)
    if category_snapshot_error:
        category_snapshot_info["error"] = category_snapshot_error
        errors.append(category_snapshot_error)
    if tag_snapshot_error:
        tag_snapshot_info["error"] = tag_snapshot_error
        errors.append(tag_snapshot_error)
    category_taxonomy: dict[str, Any] = {
        "provided": categories,
        "valid": None,
        "matched_path": None,
        "channel_root_valid": None,
    }
    tag_taxonomy: dict[str, Any] = {"provided": tags, "valid": None, "unknown": []}

    if not title:
        blockers.append("作品名称不能为空")
    elif len(title) > MAX_TITLE_LENGTH:
        errors.append(f"作品名称长度不能超过 {MAX_TITLE_LENGTH} 字符")
    if not pen_name:
        blockers.append("笔名不能为空")
    elif len(pen_name) > MAX_PEN_NAME_LENGTH:
        errors.append(f"笔名长度不能超过 {MAX_PEN_NAME_LENGTH} 字符")
    if not summary or summary == "暂无简介":
        blockers.append("作品简介必须填写正式内容，不能留空或使用“暂无简介”占位")
    elif len(summary) > MAX_SUMMARY_LENGTH:
        errors.append(f"简介长度不能超过 {MAX_SUMMARY_LENGTH} 字符")
    if not channel:
        blockers.append("频道尚未确认，须选择男频、女频或全频")
    elif channel not in ALLOWED_CHANNELS:
        errors.append(f"频道必须为男频、女频或全频，当前为 {channel or '空'}")
    if not status:
        blockers.append("作品状态尚未确认，须按事实选择连载或完结")
    elif status not in ALLOWED_STATUSES:
        errors.append(f"状态必须为连载或完结，当前为 {status or '空'}")
    if not categories:
        blockers.append("后台三级类目尚未确认，须从当前页面选择 3 项")
    elif len(categories) != 3 or any(not item for item in categories):
        errors.append(f"三级类目必须恰好填写 3 项，当前为 {len(categories)} 项")
    elif category_paths is not None:
        category_path = (categories[0], categories[1], categories[2])
        category_taxonomy["matched_path"] = list(category_path)
        category_taxonomy["valid"] = category_path in category_paths
        if category_path not in category_paths:
            errors.append("三级类目不在固定作品分类快照中，须精确填写“根分类 / 一级类目 / 二级类目”完整路径")
        if channel in {"男频", "女频"}:
            category_taxonomy["channel_root_valid"] = category_path[0] == channel
            if category_path[0] != channel:
                errors.append(f"{channel}频道只能选择以“{channel}”为根的三级类目")
        elif channel == "全频":
            category_taxonomy["channel_root_valid"] = category_path[0] in {
                item[0] for item in category_paths
            }
    if not tags:
        blockers.append("至少填写 1 个标签")
    elif tag_values is not None:
        unknown_tags = [tag for tag in tags if tag not in tag_values]
        tag_taxonomy["unknown"] = unknown_tags
        tag_taxonomy["valid"] = not unknown_tags
        if unknown_tags:
            errors.append("作品标签不在固定标签库中: " + "、".join(unknown_tags))
    for tag in custom_tags:
        if len(tag) > MAX_CUSTOM_TAG_LENGTH:
            errors.append(f"自定义标签“{tag}”长度不能超过 {MAX_CUSTOM_TAG_LENGTH} 字符")

    cover_info: dict[str, Any] = {}
    cover_value = _lookup(metadata, FIELD_ALIASES["cover"])
    if cover_value in (None, ""):
        blockers.append("缺少作品封面")
    else:
        _validate_cover(cover_value, root, errors, cover_info)

    history_images = _validate_history_images(
        _lookup(metadata, FIELD_ALIASES["history_achievement_images"]),
        root,
        errors,
    )

    manuscript_info: dict[str, Any] = {}
    manuscript_value = manuscript
    if manuscript_value is None:
        manuscript_value = _lookup(metadata, FIELD_ALIASES["manuscript"])
    if manuscript_value in (None, "") and project_root is None:
        blockers.append("缺少正文来源：须提供投稿文件或 Novel Studio 项目目录")
        manuscript_text = None
    else:
        manuscript_text = _validate_manuscript(manuscript_value, root, errors, manuscript_info)

    project_info: dict[str, Any] | None = None
    project_text_count: int | None = None
    if project_root is not None:
        project_info = validate_project_adapter(project_root)
        errors.extend(project_info["errors"])
        warnings.extend(project_info["warnings"])
        project_text_count = project_info.get("word_count")

    # 字数优先级：可读的 CLI/元数据 TXT > 项目正文 > 元数据声明值。
    word_count: int | None = None
    word_source = ""
    if manuscript_text is not None:
        word_count = _count_text_units(manuscript_text)
        word_source = "manuscript"
    elif project_text_count is not None:
        word_count = int(project_text_count)
        word_source = "project"
    else:
        declared = _lookup(metadata, FIELD_ALIASES["word_count"])
        if declared not in (None, ""):
            word_count = _int_value(declared)
            word_source = "metadata"
            if word_count is None or word_count < 0:
                errors.append("字数必须为不小于 0 的整数")
                word_count = None

    if word_count is not None:
        warnings.append(f"本地估算字数约 {word_count}，只供展示；最终以蛙蛙页面解析和提示为准，不阻断预填")
    else:
        warnings.append("未提供可计算的本地字数；上传后读取蛙蛙页面解析结果，不阻断预填")

    result: dict[str, Any] = {
        "ok": not errors and not blockers,
        "errors": errors,
        "blockers": blockers,
        "warnings": warnings,
        "metadata": {
            "schema_version": schema_version,
            "type": package_type or None,
            "title": title,
            "pen_name": pen_name,
            "summary": summary,
            "channel": channel,
            "status": status,
            "categories": categories,
            "tags": tags,
            "custom_tags": custom_tags,
            "campaign": dict(campaign) if isinstance(campaign, Mapping) else None,
            "workflow": dict(workflow) if isinstance(workflow, Mapping) else None,
        },
        "cover": cover_info,
        "history_achievement_images": history_images,
        "manuscript": manuscript_info,
        "word_count": word_count,
        "word_count_source": word_source or None,
        "taxonomy": {
            "category_snapshot": category_snapshot_info,
            "tag_snapshot": tag_snapshot_info,
            "categories": category_taxonomy,
            "tags": tag_taxonomy,
        },
    }
    if project_info is not None:
        result["project"] = project_info
    return result


def _load_metadata(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError("元数据 JSON 须为对象")
    return value


def _human_output(result: Mapping[str, Any]) -> str:
    lines = ["结果: 通过" if result.get("ok") else "结果: 未通过"]
    for label in ("errors", "blockers", "warnings"):
        values = result.get(label) or []
        if values:
            headings = {"errors": "错误:", "blockers": "阻断:", "warnings": "警告:"}
            lines.append(headings[label])
            lines.extend(f"- {item}" for item in values)
    if result.get("word_count") is not None:
        lines.append(f"字数: {result['word_count']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="蛙蛙执行就绪投稿包、稿件和固定字段预检")
    parser.add_argument("--metadata", required=True, help="投稿元数据 JSON 文件")
    parser.add_argument("--project-root", help="可选 Novel Studio 项目目录")
    parser.add_argument("--manuscript", help="可选投稿稿件（.doc/.docx/.txt）")
    parser.add_argument("--category-snapshot", help="可选作品分类快照 JSON，默认使用内置固定快照")
    parser.add_argument("--tag-snapshot", help="可选作品标签快照 JSON，默认使用内置固定快照")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    metadata_path = Path(args.metadata).expanduser().resolve()
    try:
        metadata = _load_metadata(metadata_path)
        result = validate_submission(
            metadata,
            manuscript=args.manuscript,
            project_root=args.project_root,
            base_dir=metadata_path.parent,
            category_snapshot=args.category_snapshot,
            tag_snapshot=args.tag_snapshot,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "ok": False,
            "errors": [f"无法读取元数据: {exc}"],
            "blockers": [],
            "warnings": [],
        }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_human_output(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
