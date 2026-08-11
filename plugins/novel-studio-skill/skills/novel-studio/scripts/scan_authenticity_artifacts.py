#!/usr/bin/env python3
"""只读定位中文小说中的生成痕迹候选，不判定文本来源或自动改写。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CHAPTER_HEADING_RE = re.compile(
    r"^#{1,3}\s*(第[0-9零一二三四五六七八九十百千两〇]+章[^\n]*)\s*$"
)
VISIBLE_RE = re.compile(r"[\u3400-\u9fffA-Za-z0-9]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])(?:[”」』\"']*)\s*|…{2,}")

WORKFLOW_LEAK_PATTERNS = (
    re.compile(
        r"^\s*(?:#{1,6}\s*)?(?:TODO|FIXME|写作说明|修改说明|改写说明|审稿意见|"
        r"章节控制卡|生成提示词|模型提示词|AI润色说明)\s*[:：]",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:下面|以下)(?:内容)?是(?:我)?(?:根据|按照).{0,24}(?:要求|提示)"
        r"(?:修改|润色|续写|生成)(?:后|的).{0,12}(?:章节|正文)\s*[:：]?\s*$"
    ),
    re.compile(r"^\s*<\|?(?:assistant|analysis|final|system|user)\|?>\s*$", re.IGNORECASE),
    re.compile(r"^\s*\[(?:TODO|FIXME|待补充|待续写)\]\s*$", re.IGNORECASE),
)

# 章节编号本身不是泄漏。只有它与制作/审查元数据在同一行，或在紧邻的
# 章节头部行组合出现时，才进入确定性候选，避免把正文里的普通“审查”“候选”
# 或“控制卡”单独误报为工作流泄漏。
CHAPTER_PRODUCTION_MARKER_RE = re.compile(
    r"(?:第(?:[0-9零一二三四五六七八九十百千两〇]+|X)章|"
    r"[零一二三四五六七八九十百千两〇]+章)"
)
PRODUCTION_COMBO_TERM_PATTERNS = (
    ("字段", re.compile(r"字段|field", re.IGNORECASE)),
    ("台账", re.compile(r"台账|ledger", re.IGNORECASE)),
    ("accepted", re.compile(r"accepted", re.IGNORECASE)),
    ("候选", re.compile(r"候选")),
    ("审查", re.compile(r"审查")),
    ("控制卡", re.compile(r"控制卡")),
)
PRODUCTION_STRICT_TERM_PATTERNS = (
    ("字段", re.compile(r"(?:字段|field)\s*(?:名|值|列表)?\s*[:：=]", re.IGNORECASE)),
    (
        "台账",
        re.compile(
            r"(?:待兑现|期待|承诺|长期|项目|审查).{0,6}台账|"
            r"台账\s*(?:字段|状态|条目|id)?\s*[:：=]",
            re.IGNORECASE,
        ),
    ),
    (
        "accepted",
        re.compile(
            r"(?:status|state|stage|result|状态|结论)\s*[:：=]\s*accepted\b|\baccepted\b",
            re.IGNORECASE,
        ),
    ),
    ("候选", re.compile(r"候选(?:章节|稿|版本|项|状态)?\s*[:：=]")),
    ("审查", re.compile(r"(?:读者|作者|连续性|文体|终审|复审).{0,4}审查|审查(?:状态|结论|轮次|报告|意见|记录)?\s*[:：=]")),
    ("控制卡", re.compile(r"控制卡(?:字段|模板|版本|状态)?\s*[:：=]")),
)
PRODUCTION_CONTEXT_LINE_WINDOW = 3

CONTRAST_PATTERNS = (
    re.compile(r"(?:不是|并非|不在)[^。！？!?\n]{1,55}(?:而是|却是|而在)"),
    re.compile(r"(?:是|在于)[^。！？!?\n]{1,45}[，,](?:而)?不是[^。！？!?\n]{1,45}"),
)
CONTRAST_MIN_OCCURRENCES = 3
EXPLANATORY_PATTERN = re.compile(
    r"这(?:就|也)?意味着|换句话说|归根结底|说到底|由此可见|可以看出|"
    r"本质上|真正的?问题(?:在于|是)"
)
NEGATION_PARADE_PATTERN = re.compile(
    r"(?:不是|没有|并非)[^。！？!?\n]{0,24}[，,；;]"
    r"(?:不是|没有|并非)[^。！？!?\n]{0,24}[，,；;]"
    r"(?:而是|只是|只有|却)"
)

PROCESS_TERMS = (
    "流程", "规则", "方案", "执行", "状态", "复核", "记录", "数据", "指标", "优化",
    "进度", "节点", "反馈", "闭环", "效率", "步骤", "标准", "结果", "确认", "机制",
)
ABSTRACT_TERMS = (
    "本质", "逻辑", "意义", "价值", "机制", "责任", "秩序", "边界", "选择", "现实",
    "关系", "情绪", "结论", "结构", "体系",
)
MICRO_ACTION_PATTERNS = (
    re.compile(r"喉结(?:轻轻)?(?:滚动|动了动)"),
    re.compile(r"指节(?:微微)?(?:发白|泛白)"),
    re.compile(r"呼吸(?:微微)?(?:一滞|停了一瞬)"),
    re.compile(r"瞳孔(?:骤然|微微)?(?:一缩|收缩)"),
    re.compile(r"心(?:头|里)?(?:猛地|蓦地)?一紧"),
    re.compile(r"扯了扯嘴角"),
    re.compile(r"垂下眼帘"),
    re.compile(r"攥紧(?:了)?(?:拳头|手指)"),
    re.compile(r"眼底闪过一丝"),
    re.compile(r"空气(?:仿佛|像是)?(?:凝固|安静下来)"),
)
SIMILE_MARKER_RE = re.compile(r"(?:像|仿佛|如同|好似)[^。！？!?，,；;\n]{1,36}")
TRAILER_ENDING_RE = re.compile(
    r"没人知道|谁也不知道|谁也没想到|殊不知|(?:这|一切)?才刚刚开始|"
    r"命运[^。！？!?\n]{0,8}齿轮|新的篇章|即将(?:开始|来临|降临)"
)
VERDICT_ENDING_RE = re.compile(
    r"这(?:就|也)?意味着|由此可见|归根结底|说到底|"
    r"真正的[^。！？!?\n]{0,24}是|从此"
)

REVIEW_CHECKLIST = (
    "叙述者是否复述了场景已经让读者看见的结论？",
    "隐去说话人标签后，主要人物的词汇、句长、回避方式和利益立场能否区分？",
    "人物是否都在完整、理性、正确地表达，缺少迟疑、遮掩、误判或不愿直说？",
    "抽象判断、流程和数据是否挤掉了动作、物件、身体处境与关系变化？",
    "章末情绪或选择是否由场景挣得，而不是由叙述者盖章或预告？",
    "与最近章节相比，事件结构、段落节奏、比喻和收尾方式是否再次同型？",
)

CATEGORY_META = {
    "workflow-leak": {
        "severity": "blocking",
        "reason": "正文疑似混入写作流程、提示词、待办标记，或“章节编号 + 字段/台账/accepted/候选/审查/控制卡”等制作元数据组合。",
        "review_question": "这段是否属于有意的元叙事？若不是，必须从正文移除；章节编号或普通词单独出现不构成阻断。",
    },
    "contrast-template": {
        "severity": "review",
        "reason": "同章密集使用反向定义或对比句，可能形成结论腔。",
        "review_question": "对比是否符合人物当下的说话方式，并提供了新信息？",
    },
    "explanatory-bridge": {
        "severity": "review",
        "reason": "解释性连接词可能替读者总结已经呈现的内容。",
        "review_question": "删去解释后，场景是否仍然成立且更有余味？",
    },
    "negation-parade": {
        "severity": "review",
        "reason": "连续否定后给出结论，容易形成工整的演说式表达。",
        "review_question": "这是人物独有的表达，还是作者代人物完成了论证？",
    },
    "procedural-cluster": {
        "severity": "review",
        "reason": "同一段聚集多个流程词，场景可能滑向方案或报告。",
        "review_question": "这些流程是否具体改变了某个人的时间、尊严、关系、身体、金钱或选择？",
    },
    "abstract-cluster": {
        "severity": "review",
        "reason": "同一句聚集多个抽象概念，可能压低可感知的场景信息。",
        "review_question": "能否保留必要思想，同时让它落到动作、物件、身体或选择上？",
    },
    "micro-action-density": {
        "severity": "review",
        "reason": "通用微动作密集出现，可能成为可替换的人物情绪占位符。",
        "review_question": "这些动作是否揭示该人物独有的处境，还是可以整段删除而不损失信息？",
    },
    "simile-cluster": {
        "severity": "review",
        "reason": "同一段比喻标记过密，可能让修辞盖过动作和信息。",
        "review_question": "保留最准确的一处后，其余比喻是否仍有独立功能？",
    },
    "trailer-ending": {
        "severity": "review",
        "reason": "章末使用预告片式固定表达，可能替代真实的余波或选择。",
        "review_question": "去掉预告句后，最后一个场景动作能否自行承担收束？",
    },
    "verdict-ending": {
        "severity": "review",
        "reason": "章末出现总结性判断，可能由叙述者替场景盖章。",
        "review_question": "结论是否已经被场景挣得，且符合当前叙事距离？",
    },
}


@dataclass(frozen=True)
class SourceLine:
    number: int
    text: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读定位中文小说中的流程泄漏、模板化解释和真实性修订候选"
    )
    parser.add_argument("paths", nargs="*", help="章节 Markdown/TXT 文件或目录")
    parser.add_argument("--project-root", help="Novel Studio 项目目录；优先读取 正文/ 或 chapters/")
    parser.add_argument("--chapter", type=int, help="只分析指定章节号")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--fail-on-blocking",
        action="store_true",
        help="发现确定性的工作流泄漏时退出 1；普通复核候选不改变退出码",
    )
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
            candidates.extend(
                item for item in path.rglob("*") if item.suffix.lower() in {".md", ".txt"}
            )

    unique = {path.resolve(): path.resolve() for path in candidates if path.is_file()}
    return sorted(unique.values(), key=natural_key)


def read_lines(path: Path) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        warnings.append(
            f"{path}: UTF-8 解码失败（字节 {exc.start}），已用替换字符继续扫描；结果可能不完整"
        )
        text = data.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), warnings


def mask_non_prose(raw_lines: list[str]) -> list[SourceLine]:
    result: list[SourceLine] = []
    in_frontmatter = bool(raw_lines and raw_lines[0].strip() == "---")
    in_fence = False
    in_comment = False
    for number, raw in enumerate(raw_lines, start=1):
        stripped = raw.strip()
        if in_frontmatter:
            if number > 1 and stripped == "---":
                in_frontmatter = False
            result.append(SourceLine(number, ""))
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            result.append(SourceLine(number, ""))
            continue
        if in_fence:
            result.append(SourceLine(number, ""))
            continue
        if in_comment:
            if "-->" in raw:
                in_comment = False
            result.append(SourceLine(number, ""))
            continue
        if "<!--" in raw:
            if "-->" not in raw.split("<!--", 1)[1]:
                in_comment = True
            result.append(SourceLine(number, ""))
            continue
        cleaned = re.sub(r"^\s*>\s?", "", raw)
        result.append(SourceLine(number, cleaned.rstrip()))
    return result


def split_units(lines: list[SourceLine], fallback_title: str) -> list[tuple[str, list[SourceLine]]]:
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = CHAPTER_HEADING_RE.match(line.text.strip())
        if match:
            headings.append((index, match.group(1).strip()))
    if not headings:
        return [(fallback_title, lines)]
    if len(headings) == 1:
        index, title = headings[0]
        body = lines[:index] + [SourceLine(lines[index].number, "")] + lines[index + 1 :]
        return [(title, body)]

    units: list[tuple[str, list[SourceLine]]] = []
    for position, (start, title) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        units.append((title, [SourceLine(lines[start].number, ""), *lines[start + 1 : end]]))
    return units


def parse_chinese_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    total = 0
    current = 0
    for char in value:
        if char in digits:
            current = digits[char]
        elif char in units:
            total += (current or 1) * units[char]
            current = 0
        else:
            return None
    return total + current if total or current else None


def chapter_number(path: Path, title: str, raw_lines: list[str]) -> int | None:
    title_match = re.search(r"第([0-9零一二三四五六七八九十百千两〇]+)章", title)
    if title_match:
        return parse_chinese_number(title_match.group(1))
    prefix = "\n".join(raw_lines[:40])
    frontmatter_match = re.search(r"(?m)^number:\s*[\"']?(\d+)", prefix)
    if frontmatter_match:
        return int(frontmatter_match.group(1))
    filename_match = re.search(r"(\d+)", path.stem)
    return int(filename_match.group(1)) if filename_match else None


def paragraphs(lines: list[SourceLine]) -> list[SourceLine]:
    values: list[SourceLine] = []
    current: list[str] = []
    start = 0
    for line in lines:
        text = re.sub(r"^\s*#{1,6}\s*", "", line.text).strip()
        if text:
            if not current:
                start = line.number
            current.append(text)
        elif current:
            values.append(SourceLine(start, re.sub(r"\s+", " ", " ".join(current)).strip()))
            current = []
    if current:
        values.append(SourceLine(start, re.sub(r"\s+", " ", " ".join(current)).strip()))
    return values


def sentences(paragraph: SourceLine) -> list[SourceLine]:
    return [
        SourceLine(paragraph.number, item.strip())
        for item in SENTENCE_SPLIT_RE.split(paragraph.text)
        if item.strip()
    ]


def excerpt(text: str, limit: int = 140) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1]}…"


def visible_length(text: str) -> int:
    return len(VISIBLE_RE.findall(text))


def add_evidence(
    buckets: dict[str, list[dict[str, object]]],
    category: str,
    line: int,
    text: str,
    **extra: object,
) -> None:
    item: dict[str, object] = {"line": line, "excerpt": excerpt(text)}
    item.update(extra)
    buckets[category].append(item)


def production_terms(text: str, *, strict: bool) -> list[str]:
    patterns = PRODUCTION_STRICT_TERM_PATTERNS if strict else PRODUCTION_COMBO_TERM_PATTERNS
    return [label for label, pattern in patterns if pattern.search(text)]


def production_workflow_evidence(
    title: str, lines: list[SourceLine]
) -> list[dict[str, object]]:
    """找“章节编号 + 制作元数据”的确定性组合，不把普通词单独升级为阻断。"""

    evidence: list[dict[str, object]] = []
    seen: set[tuple[int, tuple[str, ...]]] = set()

    def add(line: int, text: str, terms: list[str]) -> None:
        if not terms:
            return
        key = (line, tuple(sorted(set(terms))))
        if key in seen:
            return
        seen.add(key)
        evidence.append(
            {
                "line": line,
                "excerpt": excerpt(text),
                "matched_terms": sorted(set(terms)),
                "combination": "chapter-marker+production-metadata",
            }
        )

    marker_indexes = [
        index for index, line in enumerate(lines) if CHAPTER_PRODUCTION_MARKER_RE.search(line.text)
    ]
    for index in marker_indexes:
        line = lines[index]
        terms = production_terms(line.text, strict=False)
        if terms:
            add(line.number, line.text, terms)
        for nearby in lines[index + 1 : index + 1 + PRODUCTION_CONTEXT_LINE_WINDOW]:
            strict_terms = production_terms(nearby.text, strict=True)
            if strict_terms:
                add(nearby.number, f"{line.text} / {nearby.text}", strict_terms)

    # split_units 会把章节标题替换为空行，但 title 仍保留原始章节编号；
    # 因此也审查标题后的少量头部正文，覆盖“第十八章\nstatus: accepted”。
    if CHAPTER_PRODUCTION_MARKER_RE.search(title):
        for line in lines[:PRODUCTION_CONTEXT_LINE_WINDOW]:
            strict_terms = production_terms(line.text, strict=True)
            if strict_terms:
                add(line.number, f"{title} / {line.text}", strict_terms)

    return evidence


def scan_unit(source: Path, title: str, lines: list[SourceLine], warnings: list[str]) -> dict[str, object]:
    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    paras = paragraphs(lines)
    all_sentences = [sentence for para in paras for sentence in sentences(para)]
    contrast_evidence: list[dict[str, object]] = []

    for line in lines:
        if line.text and any(pattern.search(line.text) for pattern in WORKFLOW_LEAK_PATTERNS):
            add_evidence(buckets, "workflow-leak", line.number, line.text)

    for item in production_workflow_evidence(title, lines):
        add_evidence(
            buckets,
            "workflow-leak",
            int(item["line"]),
            str(item["excerpt"]),
            matched_terms=item["matched_terms"],
            combination=item["combination"],
        )

    for sentence in all_sentences:
        if any(pattern.search(sentence.text) for pattern in CONTRAST_PATTERNS):
            contrast_evidence.append(
                {"line": sentence.number, "excerpt": excerpt(sentence.text)}
            )
        if EXPLANATORY_PATTERN.search(sentence.text):
            add_evidence(buckets, "explanatory-bridge", sentence.number, sentence.text)
        if NEGATION_PARADE_PATTERN.search(sentence.text):
            add_evidence(buckets, "negation-parade", sentence.number, sentence.text)
        abstract = sorted({term for term in ABSTRACT_TERMS if term in sentence.text})
        if len(abstract) >= 4:
            add_evidence(
                buckets,
                "abstract-cluster",
                sentence.number,
                sentence.text,
                matched_terms=abstract,
            )

    if len(contrast_evidence) >= CONTRAST_MIN_OCCURRENCES:
        buckets["contrast-template"].extend(contrast_evidence)

    for para in paras:
        process = sorted({term for term in PROCESS_TERMS if term in para.text})
        if len(process) >= 3:
            add_evidence(
                buckets,
                "procedural-cluster",
                para.number,
                para.text,
                matched_terms=process,
            )
        similes = SIMILE_MARKER_RE.findall(para.text)
        if len(similes) >= 3:
            add_evidence(
                buckets,
                "simile-cluster",
                para.number,
                para.text,
                matched_phrases=[excerpt(item, 48) for item in similes[:5]],
            )

    micro_evidence: list[dict[str, object]] = []
    micro_counts: dict[str, int] = defaultdict(int)
    for sentence in all_sentences:
        for pattern in MICRO_ACTION_PATTERNS:
            for match in pattern.finditer(sentence.text):
                phrase = match.group(0)
                micro_counts[phrase] += 1
                micro_evidence.append(
                    {"line": sentence.number, "excerpt": excerpt(sentence.text), "matched_phrase": phrase}
                )
    if len(micro_evidence) >= 3 or any(count >= 2 for count in micro_counts.values()):
        buckets["micro-action-density"].extend(micro_evidence)

    ending_paras = paras[-2:]
    for para in ending_paras:
        if TRAILER_ENDING_RE.search(para.text):
            add_evidence(buckets, "trailer-ending", para.number, para.text)
        if VERDICT_ENDING_RE.search(para.text):
            add_evidence(buckets, "verdict-ending", para.number, para.text)

    findings: list[dict[str, object]] = []
    for category in CATEGORY_META:
        evidence = buckets.get(category, [])
        if not evidence:
            continue
        meta = CATEGORY_META[category]
        findings.append(
            {
                "category": category,
                "severity": meta["severity"],
                "occurrences": len(evidence),
                "reason": meta["reason"],
                "review_question": meta["review_question"],
                "evidence": evidence[:8],
                "evidence_truncated": max(0, len(evidence) - 8),
            }
        )

    characters = sum(visible_length(para.text) for para in paras)
    local_warnings = list(warnings)
    if characters == 0:
        local_warnings.append(f"{source}: 章节为空或不含可扫描文字")
    elif characters < 200:
        local_warnings.append(f"{source}: 章节极短（{characters} 字符），候选密度不宜跨章比较")
    blockers = sum(item["occurrences"] for item in findings if item["severity"] == "blocking")
    reviews = sum(item["occurrences"] for item in findings if item["severity"] == "review")
    return {
        "source": str(source),
        "title": title,
        "characters": characters,
        "status": "blocking" if blockers else ("review" if reviews else "no-candidates"),
        "blocking_findings": blockers,
        "review_candidates": reviews,
        "findings": findings,
        "warnings": local_warnings,
    }


def scan(files: list[Path], chapter_filter: int | None = None) -> dict[str, object]:
    chapters: list[dict[str, object]] = []
    global_warnings: list[str] = []
    for path in files:
        raw_lines, warnings = read_lines(path)
        units = split_units(mask_non_prose(raw_lines), path.stem)
        for title, unit_lines in units:
            if chapter_filter is not None and chapter_number(path, title, raw_lines) != chapter_filter:
                continue
            chapters.append(scan_unit(path, title, unit_lines, warnings))
        global_warnings.extend(warnings)

    blockers = sum(item["blocking_findings"] for item in chapters)
    reviews = sum(item["review_candidates"] for item in chapters)
    if chapter_filter is not None and not chapters:
        global_warnings.append(f"未找到第 {chapter_filter} 章")
    return {
        "ok": True,
        "read_only": True,
        "files": len(files),
        "chapters": chapters,
        "summary": {
            "blocking_findings": blockers,
            "review_candidates": reviews,
            "chapters_with_candidates": sum(
                1 for item in chapters if item["blocking_findings"] or item["review_candidates"]
            ),
        },
        "review_checklist": list(REVIEW_CHECKLIST),
        "warnings": sorted(set(global_warnings)),
        "interpretation": (
            "本工具只定位可回读证据，不判断文本是否由 AI 生成，不提供 AI 分数，也不自动改写。"
            "除 workflow-leak 外，所有命中都必须结合人物、场景和读者影响人工裁决。"
        ),
    }


def render_text(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        f"真实性只读扫描：{payload['files']} 个文件，{len(payload['chapters'])} 个章节单元",
        f"确定性泄漏 {summary['blocking_findings']} 处；需语境复核 {summary['review_candidates']} 处。",
        "命中不代表 AI 生成，也不应触发机械改写。",
    ]
    for index, chapter in enumerate(payload["chapters"], start=1):
        lines.append(
            f"{index}. {chapter['title']}｜{chapter['characters']} 字符｜"
            f"泄漏 {chapter['blocking_findings']}｜复核 {chapter['review_candidates']}"
        )
        for finding in chapter["findings"]:
            label = "阻断" if finding["severity"] == "blocking" else "复核"
            first = finding["evidence"][0]
            lines.append(
                f"   - [{label}] {finding['category']} ×{finding['occurrences']}｜"
                f"行 {first['line']}：{first['excerpt']}"
            )
    if payload["warnings"]:
        lines.append("读取提示：")
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    return "\n".join(lines)


def empty_payload(warning: str) -> dict[str, object]:
    return {
        "ok": True,
        "read_only": True,
        "files": 0,
        "chapters": [],
        "summary": {
            "blocking_findings": 0,
            "review_candidates": 0,
            "chapters_with_candidates": 0,
        },
        "review_checklist": list(REVIEW_CHECKLIST),
        "warnings": [warning],
        "interpretation": (
            "本工具只定位可回读证据，不判断文本是否由 AI 生成，不提供 AI 分数，也不自动改写。"
        ),
    }


def main() -> int:
    args = build_parser().parse_args()
    if args.chapter is not None and args.chapter < 1:
        print(json.dumps({"ok": False, "error": "--chapter 必须大于 0"}, ensure_ascii=False))
        return 2
    files = discover_files(args.paths, args.project_root)
    if not files:
        payload = empty_payload("未找到可扫描的 .md 或 .txt 章节文件")
    else:
        try:
            payload = scan(files, args.chapter)
        except OSError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else render_text(payload))
    if args.fail_on_blocking and payload["summary"]["blocking_findings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
