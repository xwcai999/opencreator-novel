#!/usr/bin/env python3
"""Shared, dependency-light helpers for OpenCreator Novel scripts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable

SCOPES = {"short", "medium", "long"}
COMPLEXITIES = {"light", "standard", "extended"}
DRIVERS = {
    "growth",
    "relationship",
    "business",
    "information",
    "experiential",
    "thematic",
    "quest",
}
FORBIDDEN_TITLE_PATTERNS = (
    re.compile(r"(?:作者|笔名|署名|著者)\s*[:：]", re.IGNORECASE),
    re.compile(r"(?:\s|[》】）)])[^\s]{1,30}\s*(?:著|作品)\s*$", re.IGNORECASE),
    re.compile(r"\s+by\s+[^\s].*$", re.IGNORECASE),
    re.compile(r"(?:author|byline|pen[-_ ]?name)\s*[:：]", re.IGNORECASE),
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_book_title(value: str) -> str:
    """Return a canonical book title and reject explicit attribution syntax."""
    title = value.strip()
    if not title:
        raise ValueError("书名不能为空")
    if "\n" in title or "\r" in title:
        raise ValueError("书名不能包含换行")
    if any(pattern.search(title) for pattern in FORBIDDEN_TITLE_PATTERNS):
        raise ValueError("书名疑似混入作者、笔名或署名；封面书名必须只含作品标题")
    return title


def project_id(title: str) -> str:
    digest = hashlib.sha1(title.strip().encode("utf-8")).hexdigest()[:10]
    return f"book-{digest}"


def stable_id(prefix: str, value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    if not slug:
        slug = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{slug}"


def ensure_empty_target(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"目标路径不是目录: {path}")
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"目标目录非空，拒绝覆盖: {path}")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def render_template(path: Path, values: dict[str, str]) -> str:
    content = read_text(path)
    for key, value in values.items():
        content = content.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"\{\{([a-z_]+)\}\}", content)))
    if unresolved:
        raise ValueError(f"模板仍有未解析变量 {unresolved}: {path}")
    return content


def _fallback_scalar(raw: str) -> Any:
    value = raw.strip()
    if value in {'""', "''"}:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    lower = value.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_fallback_scalar(item) for item in inner.split(",")]
    return value


def _fallback_yaml(header: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    active_list: str | None = None
    for line in header.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and active_list:
            result.setdefault(active_list, []).append(_fallback_scalar(stripped[1:]))
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", stripped)
        if not match:
            continue
        key, raw = match.groups()
        if raw:
            result[key] = _fallback_scalar(raw)
            active_list = None
        else:
            result[key] = []
            active_list = key
    return result


def parse_frontmatter_text(text: str, label: str = "document") -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError(f"缺少 YAML frontmatter: {label}")
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"frontmatter 未闭合: {label}")
    header = normalized[4:end]
    body = normalized[end + 5 :]
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(header) or {}
    except ImportError:
        parsed = _fallback_yaml(header)
    except Exception as exc:
        raise ValueError(f"frontmatter 解析失败 {label}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"frontmatter 必须是对象: {label}")
    return parsed, body


def parse_document(path: Path) -> tuple[dict[str, Any], str]:
    return parse_frontmatter_text(read_text(path), str(path))


def as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return value
    return [value]


def markdown_files(root: Path, excluded_top: Iterable[str] = ("索引", "报告", "封面")) -> list[Path]:
    excluded = set(excluded_top)
    files = []
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in excluded:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def chapter_number(path: Path, metadata: dict[str, Any] | None = None) -> int:
    if metadata and metadata.get("number") not in (None, ""):
        try:
            return int(metadata["number"])
        except (TypeError, ValueError):
            return 0
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def text_units(body: str) -> int:
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    cjk = re.findall(r"[\u3400-\u9fff]", body)
    words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", body)
    return len(cjk) + len(words)


def is_kebab_id(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", value))


def ensure_within(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"路径越界: {resolved}") from exc
    return resolved
