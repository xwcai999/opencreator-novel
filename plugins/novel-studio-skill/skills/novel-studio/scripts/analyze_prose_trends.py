#!/usr/bin/env python3
"""只读分析中文小说的文体趋势，输出证据而不判定文学好坏。"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


ANALYTICAL_TERMS = (
    "本质", "逻辑", "机制", "结构", "体系", "意味着", "核心", "真正", "显然",
    "换句话说", "归根结底", "可以看出", "事实上", "结论", "价值", "意义",
)
PROCESS_TERMS = (
    "流程", "规则", "方案", "执行", "状态", "复核", "记录", "数据", "指标", "优化",
    "进度", "节点", "反馈", "闭环", "效率", "步骤", "标准", "结果", "确认", "机制",
)
PATTERNS = {
    "不是_而是": re.compile(r"不是[^。！？!?\n]{0,45}而是"),
    "不等于": re.compile(r"不等于"),
    "真正的_是": re.compile(r"真正的?[^。！？!?\n]{0,25}是"),
    "问题不在_而在": re.compile(r"问题不在[^。！？!?\n]{0,35}而在"),
    "这意味着": re.compile(r"这意味着"),
    "与其_不如": re.compile(r"与其[^。！？!?\n]{0,35}不如"),
}
ENDING_PATTERNS = {
    "转义式_不是而是": re.compile(r"不是[^。！？!?\n]{0,55}而是"),
    "定义式_真正是": re.compile(r"真正的?[^。！？!?\n]{0,35}是"),
    "解释式_意味着": re.compile(r"这意味着|也就是说|换句话说"),
    "领悟式": re.compile(r"终于明白|忽然明白|这才明白|她明白了|他明白了"),
    "未来总结式": re.compile(r"从此|以后会|接下来|未来|新的开始"),
}
QUOTE_RE = re.compile(r"[“「『](.*?)[”」』]|\"([^\"\n]+)\"", re.DOTALL)
CHAPTER_HEADING_RE = re.compile(
    r"(?m)^#{1,3}\s*(第[0-9零一二三四五六七八九十百千两〇]+章[^\n]*)\s*$"
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])(?:[”」』\"']*)\s*|…{2,}")
VISIBLE_RE = re.compile(r"[\u3400-\u9fffA-Za-z0-9]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读分析中文小说对白、段落、重复句式、章末结构和分析腔趋势"
    )
    parser.add_argument("paths", nargs="*", help="章节 Markdown 文件或目录")
    parser.add_argument("--project-root", help="OpenCreator Novel 项目目录；优先分析其中的 正文/ 或 chapters/")
    parser.add_argument("--window-size", type=int, help="跨章窗口大小；默认把全书约分为四段")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def natural_key(path: Path) -> tuple[int, str]:
    numbers = re.findall(r"\d+", path.stem)
    return (int(numbers[0]) if numbers else 10**9, path.as_posix().lower())


def discover_files(raw_paths: Iterable[str], project_root: str | None) -> list[Path]:
    candidates: list[Path] = []
    if project_root:
        root = Path(project_root).expanduser().resolve()
        for relative in ("正文", "chapters"):
            chapter_dir = root / relative
            if chapter_dir.is_dir():
                candidates.extend(chapter_dir.rglob("*.md"))
                break
        else:
            if root.is_dir():
                candidates.extend(root.glob("*.md"))

    for value in raw_paths:
        path = Path(value).expanduser().resolve()
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            candidates.append(path)
        elif path.is_dir():
            candidates.extend(item for item in path.rglob("*") if item.suffix.lower() in {".md", ".txt"})

    unique = {path.resolve(): path.resolve() for path in candidates if path.is_file()}
    return sorted(unique.values(), key=natural_key)


def read_text(path: Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig", errors="strict"), warnings
    except UnicodeDecodeError as exc:
        warnings.append(
            f"{path}: UTF-8 解码失败（字节 {exc.start}），已用替换字符继续统计；相关计数可能偏低"
        )
        return data.decode("utf-8-sig", errors="replace"), warnings


def strip_markdown(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.startswith("---\n"):
        end = normalized.find("\n---\n", 4)
        if end >= 0:
            normalized = normalized[end + 5 :]
    normalized = re.sub(r"```.*?```", "", normalized, flags=re.DOTALL)
    normalized = re.sub(r"<!--.*?-->", "", normalized, flags=re.DOTALL)
    normalized = re.sub(r"(?m)^\s*#{1,6}\s*", "", normalized)
    normalized = re.sub(r"(?m)^\s*>\s?", "", normalized)
    return normalized.strip()


def split_embedded_chapters(text: str, fallback_title: str) -> list[tuple[str, str]]:
    matches = list(CHAPTER_HEADING_RE.finditer(text))
    if len(matches) < 2:
        return [(fallback_title, text)]
    units: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        units.append((match.group(1).strip(), text[start:end].strip()))
    return units


def visible_length(text: str) -> int:
    return len(VISIBLE_RE.findall(text))


def paragraphs(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", text) if item.strip()]


def sentences(text: str) -> list[str]:
    return [item.strip() for item in SENTENCE_SPLIT_RE.split(text) if item.strip()]


def dialogue_segments(text: str) -> list[str]:
    values: list[str] = []
    for match in QUOTE_RE.finditer(text):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        if value and value.strip():
            values.append(value.strip())
    return values


def term_evidence(text: str, terms: tuple[str, ...]) -> dict[str, int]:
    counts = {term: text.count(term) for term in terms}
    return {term: count for term, count in counts.items() if count}


def sentence_openers(items: list[str]) -> list[dict[str, object]]:
    openers: list[str] = []
    for item in items:
        cleaned = re.sub(r"^[\s“”「」『』\"'，,：:；;—-]+", "", item)
        token = "".join(VISIBLE_RE.findall(cleaned))[:8]
        if len(token) >= 2:
            openers.append(token)
    return [
        {"text": text, "count": count}
        for text, count in Counter(openers).most_common(5)
        if count >= 2
    ]


def ending_evidence(items: list[str]) -> dict[str, object]:
    ending = "\n".join(items[-2:]) if items else ""
    categories = [name for name, pattern in ENDING_PATTERNS.items() if pattern.search(ending)]
    final_sentences = sentences(ending)
    final = final_sentences[-1] if final_sentences else ending
    normalized = "".join(VISIBLE_RE.findall(final))[-40:]
    return {
        "categories": categories,
        "final_sentence_excerpt": final.strip()[-80:],
        "normalized_tail": normalized,
    }


def analyze_unit(source: Path, title: str, text: str, warnings: list[str]) -> dict[str, object]:
    body = strip_markdown(text)
    paras = paragraphs(body)
    sents = sentences(body)
    dialogues = dialogue_segments(body)
    total_chars = visible_length(body)
    dialogue_chars = sum(visible_length(item) for item in dialogues)
    para_lengths = [visible_length(item) for item in paras]
    single_sentence = sum(1 for item in paras if len(sentences(item)) <= 1)
    analytical = term_evidence(body, ANALYTICAL_TERMS)
    process = term_evidence(body, PROCESS_TERMS)
    pattern_counts = {name: len(pattern.findall(body)) for name, pattern in PATTERNS.items()}
    pattern_counts = {name: count for name, count in pattern_counts.items() if count}
    local_warnings = list(warnings)
    if total_chars == 0:
        local_warnings.append(f"{source}: 章节为空或不含可统计文字")
    elif total_chars < 200:
        local_warnings.append(f"{source}: 章节极短（{total_chars} 字符），比例波动不宜作跨章结论")

    per_1000 = lambda count: round(count * 1000 / total_chars, 3) if total_chars else 0.0
    return {
        "source": str(source),
        "title": title,
        "characters": total_chars,
        "paragraphs": len(paras),
        "sentences": len(sents),
        "dialogue": {
            "turns": len(dialogues),
            "characters": dialogue_chars,
            "ratio": round(dialogue_chars / total_chars, 4) if total_chars else 0.0,
        },
        "paragraph_rhythm": {
            "median_characters": round(statistics.median(para_lengths), 2) if para_lengths else 0.0,
            "mean_characters": round(statistics.mean(para_lengths), 2) if para_lengths else 0.0,
            "max_characters": max(para_lengths, default=0),
            "single_sentence_ratio": round(single_sentence / len(paras), 4) if paras else 0.0,
        },
        "analytical_language": {
            "count": sum(analytical.values()),
            "per_1000_characters": per_1000(sum(analytical.values())),
            "terms": analytical,
        },
        "process_language": {
            "count": sum(process.values()),
            "per_1000_characters": per_1000(sum(process.values())),
            "terms": process,
        },
        "repeated_structures": {
            "pattern_counts": pattern_counts,
            "repeated_sentence_openers": sentence_openers(sents),
        },
        "ending": ending_evidence(paras),
        "warnings": local_warnings,
    }


def make_windows(chapters: list[dict[str, object]], requested_size: int | None) -> list[dict[str, object]]:
    if not chapters:
        return []
    size = requested_size or max(1, math.ceil(len(chapters) / 4))
    windows: list[dict[str, object]] = []
    for start in range(0, len(chapters), size):
        group = chapters[start : start + size]
        windows.append(
            {
                "chapter_range": [start + 1, start + len(group)],
                "titles": [item["title"] for item in group],
                "dialogue_ratio_mean": round(
                    statistics.mean(item["dialogue"]["ratio"] for item in group), 4
                ),
                "analytical_per_1000_mean": round(
                    statistics.mean(item["analytical_language"]["per_1000_characters"] for item in group), 3
                ),
                "process_per_1000_mean": round(
                    statistics.mean(item["process_language"]["per_1000_characters"] for item in group), 3
                ),
                "paragraph_median_mean": round(
                    statistics.mean(item["paragraph_rhythm"]["median_characters"] for item in group), 2
                ),
            }
        )
    return windows


def cross_chapter_evidence(chapters: list[dict[str, object]]) -> dict[str, object]:
    endings = Counter(
        category
        for chapter in chapters
        for category in chapter["ending"]["categories"]
    )
    repeated_endings = [
        {"category": category, "chapters": count}
        for category, count in endings.most_common()
        if count >= 2
    ]
    tails = Counter(
        chapter["ending"]["normalized_tail"]
        for chapter in chapters
        if chapter["ending"]["normalized_tail"]
    )
    exact_tails = [
        {"tail": tail, "chapters": count}
        for tail, count in tails.most_common(5)
        if count >= 2
    ]
    return {
        "repeated_ending_categories": repeated_endings,
        "repeated_exact_tails": exact_tails,
    }


def analyze(files: list[Path], window_size: int | None = None) -> dict[str, object]:
    chapters: list[dict[str, object]] = []
    global_warnings: list[str] = []
    for path in files:
        raw, warnings = read_text(path)
        units = split_embedded_chapters(raw, path.stem)
        for title, text in units:
            chapters.append(analyze_unit(path, title, text, warnings))
            global_warnings.extend(warnings)
    return {
        "ok": True,
        "read_only": True,
        "files": len(files),
        "chapters": chapters,
        "windows": make_windows(chapters, window_size),
        "cross_chapter_evidence": cross_chapter_evidence(chapters),
        "warnings": sorted(set(global_warnings)),
        "interpretation": "所有指标仅提供回读证据，不直接判定文学好坏、章节通过或失败。",
    }


def render_text(payload: dict[str, object]) -> str:
    lines = [
        f"只读分析：{payload['files']} 个文件，{len(payload['chapters'])} 个章节单元",
        "指标仅用于定位回读证据，不构成文学好坏判定。",
    ]
    for index, chapter in enumerate(payload["chapters"], start=1):
        lines.append(
            f"{index}. {chapter['title']}｜{chapter['characters']} 字符｜"
            f"对白 {chapter['dialogue']['ratio']:.1%}｜"
            f"分析词 {chapter['analytical_language']['per_1000_characters']}/千字｜"
            f"流程词 {chapter['process_language']['per_1000_characters']}/千字"
        )
    if payload["windows"]:
        lines.append("跨章窗口：")
        for window in payload["windows"]:
            start, end = window["chapter_range"]
            lines.append(
                f"- {start}-{end}：对白均值 {window['dialogue_ratio_mean']:.1%}，"
                f"分析词 {window['analytical_per_1000_mean']}/千字，"
                f"流程词 {window['process_per_1000_mean']}/千字"
            )
    warnings = sorted({warning for chapter in payload["chapters"] for warning in chapter["warnings"]})
    if warnings:
        lines.append("读取提示：")
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()
    if args.window_size is not None and args.window_size < 1:
        print(json.dumps({"ok": False, "error": "--window-size 必须大于 0"}, ensure_ascii=False))
        return 2
    files = discover_files(args.paths, args.project_root)
    if not files:
        payload = {
            "ok": True,
            "read_only": True,
            "files": 0,
            "chapters": [],
            "windows": [],
            "cross_chapter_evidence": {
                "repeated_ending_categories": [],
                "repeated_exact_tails": [],
            },
            "warnings": ["未找到可分析的 .md 或 .txt 章节文件"],
            "interpretation": "所有指标仅提供回读证据，不直接判定文学好坏、章节通过或失败。",
        }
    else:
        try:
            payload = analyze(files, args.window_size)
        except OSError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
