#!/usr/bin/env python3
"""只读定位跨章投稿风险候选，不给文学 PASS/FAIL，也不修改正文。"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from analyze_prose_trends import (
    ENDING_PATTERNS,
    PROCESS_TERMS,
    QUOTE_RE,
    discover_files,
    paragraphs,
    read_text,
    sentences,
    split_embedded_chapters,
    strip_markdown,
    visible_length,
)


BOARD_RECORD_TERMS = ("白板", "记录", "表格", "台账", "控制卡")
STRUCTURE_PATTERNS = {
    "目标": re.compile(r"订单|需求|目标|决定|要(?:做|接|去)|必须"),
    "阻力": re.compile(r"问题|偏差|不行|不能|失败|异常|停机|返工|拒绝|卡住"),
    "流程": re.compile(r"流程|方案|步骤|复核|记录|表格|试验|节点|调整|确认"),
    "收束": re.compile(r"通过|完成|稳定|合格|签字|达标|解决|继续|下一步"),
}
SPEAKER_RE = re.compile(
    r"(?:^|[\n。！？!?，,；;：:”“「」])\s*(?P<name>[\u3400-\u9fff]{2,3})"
    r"(?:说道|说着|说|问道|问|答道|答|回答|补充|喊道|喊|低声道|笑道|回道|开口|接话|解释|提醒)"
)
SPEAKER_MIN_OCCURRENCES = 2
SPEAKER_BAD_ENDINGS = frozenset("回想看来说问答补笑低喊开接道是没才就着先也而前后")
SPEAKER_BAD_PHRASES = frozenset({"也没有", "以后谁", "你不是", "所以才", "没有先", "谁也没"})
CHAPTER_NUMBER_RE = re.compile(r"第([0-9零一二三四五六七八九十百千两〇]+)章")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读分析跨章出版风险：锚点缺失、流程密度、章末收束、重复结构与声线盲测输入"
    )
    parser.add_argument("paths", nargs="*", help="章节 Markdown/TXT 文件或目录")
    parser.add_argument(
        "--project-root",
        help="OpenCreator Novel 项目目录；优先读取其中的 正文/ 或 chapters/",
    )
    parser.add_argument(
        "--anchor",
        "--target-anchor",
        dest="anchors",
        action="append",
        default=[],
        help="目标锚点，可重复；只报告前后章节出现而中间缺失的候选",
    )
    parser.add_argument(
        "--process-threshold",
        type=float,
        default=18.0,
        help="流程词密度候选阈值（每千字），默认 18",
    )
    parser.add_argument(
        "--board-record-threshold",
        type=float,
        default=3.0,
        help="白板/记录类词密度候选阈值（每千字），默认 3",
    )
    parser.add_argument(
        "--max-voice-samples",
        type=int,
        default=2,
        help="每个可识别说话人最多输出的盲测样本数，默认 2",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def parse_chapter_number(title: str, fallback: int) -> int:
    match = CHAPTER_NUMBER_RE.search(title)
    if not match:
        return fallback
    value = match.group(1)
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
            return fallback
    return total + current if total or current else fallback


def load_chapters(files: list[Path]) -> tuple[list[dict[str, object]], list[str]]:
    chapters: list[dict[str, object]] = []
    warnings: list[str] = []
    for path in files:
        raw, local_warnings = read_text(path)
        warnings.extend(local_warnings)
        units = split_embedded_chapters(raw, path.stem)
        for title, text in units:
            body = strip_markdown(text)
            chapters.append(
                {
                    "index": len(chapters) + 1,
                    "chapter_number": parse_chapter_number(title, len(chapters) + 1),
                    "title": title,
                    "source": str(path),
                    "text": body,
                }
            )
    return chapters, sorted(set(warnings))


def per_1000(count: int, characters: int) -> float:
    return round(count * 1000 / characters, 3) if characters else 0.0


def term_counts(text: str, terms: Iterable[str]) -> dict[str, int]:
    return {term: count for term, count in ((term, text.count(term)) for term in terms) if count}


def target_anchor_risks(chapters: list[dict[str, object]], anchors: list[str]) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    coverage: list[dict[str, object]] = []
    for raw_anchor in anchors:
        anchor = re.sub(r"\s+", " ", raw_anchor).strip()
        if not anchor:
            continue
        present = [
            int(chapter["index"])
            for chapter in chapters
            if anchor.casefold() in str(chapter["text"]).casefold()
        ]
        coverage.append(
            {
                "anchor": anchor,
                "present_chapters": present,
                "first_chapter": min(present) if present else None,
                "last_chapter": max(present) if present else None,
            }
        )
        if len(present) < 2:
            continue
        present_set = set(present)
        first, last = min(present), max(present)
        for chapter in chapters:
            index = int(chapter["index"])
            if first < index < last and index not in present_set:
                candidates.append(
                    {
                        "anchor": anchor,
                        "chapter": index,
                        "chapter_number": chapter["chapter_number"],
                        "title": chapter["title"],
                        "source": chapter["source"],
                        "first_seen": first,
                        "last_seen": last,
                        "reason": "锚点在前后章节出现，但本章缺失；需人工确认是否为有意冷藏。",
                    }
                )
    return {"coverage": coverage, "candidates": candidates}


def process_density_risks(
    chapters: list[dict[str, object]],
    process_threshold: float,
    board_record_threshold: float,
) -> dict[str, object]:
    per_chapter: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for chapter in chapters:
        text = str(chapter["text"])
        chars = visible_length(text)
        process = term_counts(text, PROCESS_TERMS)
        board_record = term_counts(text, BOARD_RECORD_TERMS)
        process_total = sum(process.values())
        board_record_total = sum(board_record.values())
        process_rate = per_1000(process_total, chars)
        board_record_rate = per_1000(board_record_total, chars)
        reasons: list[str] = []
        if process_rate >= process_threshold:
            reasons.append("流程词过密")
        if board_record_rate >= board_record_threshold:
            reasons.append("白板/记录类词过密")
        item = {
            "chapter": chapter["index"],
            "chapter_number": chapter["chapter_number"],
            "title": chapter["title"],
            "characters": chars,
            "process_count": process_total,
            "process_per_1000": process_rate,
            "process_terms": process,
            "board_record_count": board_record_total,
            "board_record_per_1000": board_record_rate,
            "board_record_terms": board_record,
            "reasons": reasons,
        }
        per_chapter.append(item)
        if reasons:
            candidates.append(item)
    return {
        "thresholds": {
            "process_per_1000": process_threshold,
            "board_record_per_1000": board_record_threshold,
        },
        "chapters": per_chapter,
        "candidates": candidates,
    }


def chapter_end_risks(chapters: list[dict[str, object]]) -> list[dict[str, object]]:
    risks: list[dict[str, object]] = []
    for chapter in chapters:
        paras = paragraphs(str(chapter["text"]))
        ending = "\n".join(paras[-2:]) if paras else ""
        categories = [
            name for name, pattern in ENDING_PATTERNS.items() if pattern.search(ending)
        ]
        marker_counts = {
            "completion": len(re.findall(r"通过|完成|合格|签字|交付|验收", ending)),
            "reflection": len(re.findall(r"明白|意识到|知道|这意味着|真正的", ending)),
            "future": len(re.findall(r"下一步|以后|未来|接下来|新的?", ending)),
        }
        active_markers = [name for name, count in marker_counts.items() if count]
        if len(categories) < 2 and len(active_markers) < 2:
            continue
        risks.append(
            {
                "chapter": chapter["index"],
                "chapter_number": chapter["chapter_number"],
                "title": chapter["title"],
                "categories": categories,
                "marker_counts": marker_counts,
                "evidence": [item[:220] for item in paras[-2:]],
                "reason": "章末同时出现多种总结/领悟/未来预告收束信号，需人工回读最后一个有效动作。",
            }
        )
    return risks


def structure_signature(text: str) -> tuple[str, ...]:
    labels: list[str] = []
    for sentence in sentences(text):
        matched = [label for label, pattern in STRUCTURE_PATTERNS.items() if pattern.search(sentence)]
        if not matched:
            continue
        label = matched[0]
        if not labels or labels[-1] != label:
            labels.append(label)
    ordered = [label for label in STRUCTURE_PATTERNS if label in labels]
    if all(label in labels for label in STRUCTURE_PATTERNS):
        return tuple(ordered)
    return tuple(labels[:6])


def repeated_structure_risks(chapters: list[dict[str, object]]) -> dict[str, object]:
    by_signature: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    chapter_signatures: list[dict[str, object]] = []
    for chapter in chapters:
        signature = structure_signature(str(chapter["text"]))
        item = {
            "chapter": chapter["index"],
            "chapter_number": chapter["chapter_number"],
            "title": chapter["title"],
            "signature": list(signature),
        }
        chapter_signatures.append(item)
        if len(signature) >= 3:
            by_signature[signature].append(item)
    groups = [
        {
            "signature": list(signature),
            "chapters": [item["chapter"] for item in items],
            "titles": [item["title"] for item in items],
            "count": len(items),
            "reason": "多个章节出现相同的目标—阻力—流程—收束顺序；仅作回读候选。",
        }
        for signature, items in by_signature.items()
        if len(items) >= 3
    ]
    return {"chapter_signatures": chapter_signatures, "groups": groups}


def voice_blind_test_inputs(
    chapters: list[dict[str, object]], max_per_speaker: int
) -> dict[str, object]:
    raw_samples_by_speaker: dict[str, list[dict[str, object]]] = defaultdict(list)
    for chapter in chapters:
        text = str(chapter["text"])
        for match in QUOTE_RE.finditer(text):
            quote = match.group(1) if match.group(1) is not None else match.group(2)
            if not quote or not (8 <= visible_length(quote.strip()) <= 140):
                continue
            context = text[max(0, match.start() - 80) : match.start()]
            speaker_match = list(SPEAKER_RE.finditer(context))
            if not speaker_match:
                continue
            speaker = speaker_match[-1].group("name")
            raw_samples_by_speaker[speaker].append(
                {
                    "chapter": chapter["index"],
                    "chapter_number": chapter["chapter_number"],
                    "text": quote.strip(),
                }
            )

    samples_by_speaker = {
        speaker: samples
        for speaker, samples in raw_samples_by_speaker.items()
        if len(samples) >= SPEAKER_MIN_OCCURRENCES
        and speaker not in SPEAKER_BAD_PHRASES
        and speaker[-1:] not in SPEAKER_BAD_ENDINGS
    }
    speaker_ids = {speaker: f"character-{index:02d}" for index, speaker in enumerate(samples_by_speaker, start=1)}
    inputs: list[dict[str, object]] = []
    for speaker, samples in samples_by_speaker.items():
        for sample_index, sample in enumerate(samples[: max(0, max_per_speaker)], start=1):
            inputs.append(
                {
                    "sample_id": f"{speaker_ids[speaker]}-sample-{sample_index:02d}",
                    "character_id": speaker_ids[speaker],
                    "chapter": sample["chapter"],
                    "chapter_number": sample["chapter_number"],
                    "text": sample["text"],
                    "instruction": "隐藏人物姓名，仅凭词汇、句长、回避方式和利益立场判断是否像同一声音。",
                }
            )
    return {
        "inputs": inputs,
        "speaker_count": len(speaker_ids),
        "sample_count": len(inputs),
        "character_ids": list(speaker_ids.values()),
        "minimum_occurrences": SPEAKER_MIN_OCCURRENCES,
        "warnings": (["可识别说话人不足两个，盲测对比有限。"] if len(speaker_ids) < 2 else []),
    }


def analyze(
    files: list[Path],
    anchors: list[str],
    process_threshold: float,
    board_record_threshold: float,
    max_voice_samples: int,
) -> dict[str, object]:
    chapters, warnings = load_chapters(files)
    anchors_result = target_anchor_risks(chapters, anchors)
    process_result = process_density_risks(chapters, process_threshold, board_record_threshold)
    ending_result = chapter_end_risks(chapters)
    structure_result = repeated_structure_risks(chapters)
    voice_result = voice_blind_test_inputs(chapters, max_voice_samples)
    warnings = sorted(set(warnings + voice_result["warnings"]))
    publication_risk = {
        "target_anchor_missing_candidates": anchors_result["candidates"],
        "target_anchor_coverage": anchors_result["coverage"],
        "process_density": process_result,
        "chapter_end_multiple_closures": ending_result,
        "repeated_structures": structure_result,
        "voice_blind_test_inputs": voice_result["inputs"],
        "voice_blind_test_summary": {
            key: value for key, value in voice_result.items() if key != "inputs"
        },
    }
    return {
        "ok": True,
        "read_only": True,
        "files": len(files),
        "chapters": len(chapters),
        "publication_risk": publication_risk,
        "summary": {
            "target_anchor_missing_candidates": len(anchors_result["candidates"]),
            "process_density_candidates": len(process_result["candidates"]),
            "chapter_end_multiple_closures": len(ending_result),
            "repeated_structure_groups": len(structure_result["groups"]),
            "voice_blind_test_inputs": len(voice_result["inputs"]),
        },
        "warnings": warnings,
        "interpretation": (
            "本工具只输出出版风险回读候选和声线盲测输入，不给文学 PASS/FAIL，"
            "不判断文本来源，不自动改写，也不把普通指标直接升级为阅读阻断。"
        ),
    }


def empty_payload(warning: str) -> dict[str, object]:
    return {
        "ok": True,
        "read_only": True,
        "files": 0,
        "chapters": 0,
        "publication_risk": {
            "target_anchor_missing_candidates": [],
            "target_anchor_coverage": [],
            "process_density": {"thresholds": {}, "chapters": [], "candidates": []},
            "chapter_end_multiple_closures": [],
            "repeated_structures": {"chapter_signatures": [], "groups": []},
            "voice_blind_test_inputs": [],
            "voice_blind_test_summary": {"speaker_count": 0, "sample_count": 0, "character_ids": []},
        },
        "summary": {
            "target_anchor_missing_candidates": 0,
            "process_density_candidates": 0,
            "chapter_end_multiple_closures": 0,
            "repeated_structure_groups": 0,
            "voice_blind_test_inputs": 0,
        },
        "warnings": [warning],
        "interpretation": "本工具只输出出版风险回读候选，不给文学 PASS/FAIL。",
    }


def render_text(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        f"出版风险只读分析：{payload['files']} 个文件，{payload['chapters']} 个章节",
        "不提供文学 PASS/FAIL；以下均需回读正文裁决。",
        f"锚点缺失候选 {summary['target_anchor_missing_candidates']}；",
        f"流程/白板记录过密 {summary['process_density_candidates']}；",
        f"章末多重收束 {summary['chapter_end_multiple_closures']}；",
        f"重复结构组 {summary['repeated_structure_groups']}；",
        f"声线盲测输入 {summary['voice_blind_test_inputs']}。",
    ]
    risk = payload["publication_risk"]
    for item in risk["target_anchor_missing_candidates"]:
        lines.append(
            f"- 锚点缺失：第{item['chapter']}单元缺少“{item['anchor']}”"
            f"（前后出现于第{item['first_seen']}—{item['last_seen']}单元）"
        )
    for item in risk["chapter_end_multiple_closures"]:
        lines.append(
            f"- 章末多重收束：第{item['chapter']}单元｜{','.join(item['categories']) or '多类总结信号'}"
        )
    if payload["warnings"]:
        lines.append("读取提示：")
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()
    if args.process_threshold < 0 or args.board_record_threshold < 0:
        print(json.dumps({"ok": False, "error": "密度阈值不能小于 0"}, ensure_ascii=False))
        return 2
    if args.max_voice_samples < 0:
        print(json.dumps({"ok": False, "error": "--max-voice-samples 不能小于 0"}, ensure_ascii=False))
        return 2
    files = discover_files(args.paths, args.project_root)
    if not files:
        payload = empty_payload("未找到可分析的 .md 或 .txt 章节文件")
    else:
        try:
            payload = analyze(
                files,
                args.anchors,
                args.process_threshold,
                args.board_record_threshold,
                args.max_voice_samples,
            )
        except OSError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
