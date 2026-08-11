#!/usr/bin/env python3
"""Safely promote a model-evaluated or user-confirmed style profile draft."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from studio_common import (
    as_list,
    atomic_write_text,
    ensure_within,
    is_kebab_id,
    parse_document,
    read_text,
    sha256_text,
    text_units,
)

REQUIRED_HEADINGS = ("## 叙事声音", "## 场景表达", "## 稳定偏好")
PLACEHOLDERS = ("待确认", "当前为未激活模板")
CANDIDATE_LABELS = {"A", "B", "C"}
CANDIDATE_ORDER = ("A", "B", "C")
RUBRIC = (
    "target-reader-fit",
    "voice-distinctiveness",
    "cross-chapter-sustainability",
    "character-elasticity",
    "ai-artifact-risk",
)
BORDA_WEIGHTS = (3, 2, 1)
MAX_EVALUATION_BYTES = 256 * 1024


def _resolve_project_path(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _validate_calibration(report: Path, project: str) -> tuple[dict[str, Any], str, str]:
    metadata, body = parse_document(report)
    if metadata.get("type") != "style-calibration":
        raise ValueError("校准报告 type 必须为 style-calibration")
    if metadata.get("project") != project:
        raise ValueError("校准报告 project 与当前项目不一致")
    calibration_id = str(metadata.get("calibration-id") or "")
    if not is_kebab_id(calibration_id):
        raise ValueError("校准报告 calibration-id 必须为 ASCII kebab-case")
    if metadata.get("blind-labels") is not True:
        raise ValueError("校准报告必须声明 blind-labels: true")
    candidates = {str(item).upper() for item in as_list(metadata.get("candidates"))}
    if candidates != CANDIDATE_LABELS:
        raise ValueError("校准报告 candidates 必须恰好为 A、B、C")
    selected = str(metadata.get("selected-candidate") or "").strip().upper()
    evaluation_mode = str(metadata.get("evaluation-mode") or "user").strip().lower()
    if evaluation_mode == "ai-panel":
        if metadata.get("status") != "evaluated":
            raise ValueError("模型评审报告 status 必须为 evaluated")
        if selected not in CANDIDATE_LABELS:
            raise ValueError("模型评审 selected-candidate 必须为 A、B 或 C")
        if as_list(metadata.get("mix-sources")):
            raise ValueError("模型评审不得自动生成 mixed 文风")
        evaluation_name = str(metadata.get("evaluation-file") or "").strip()
        if (
            not evaluation_name
            or Path(evaluation_name).name != evaluation_name
            or Path(evaluation_name).suffix.lower() != ".json"
        ):
            raise ValueError("模型评审报告必须声明同目录 JSON evaluation-file")
    elif evaluation_mode == "user":
        if metadata.get("status") != "confirmed":
            raise ValueError("人工选择报告 status 必须为 confirmed")
        if selected not in CANDIDATE_LABELS | {"MIXED"}:
            raise ValueError("selected-candidate 必须为 A、B、C 或 mixed")
    else:
        raise ValueError("evaluation-mode 必须为 ai-panel 或 user")
    if evaluation_mode == "user" and selected == "MIXED":
        sources = {str(item).upper() for item in as_list(metadata.get("mix-sources"))}
        if len(sources) < 2 or not sources.issubset(CANDIDATE_LABELS):
            raise ValueError("mixed 必须在 mix-sources 中列出至少两个有效候选")
    if text_units(body) < 30:
        raise ValueError("校准报告正文过短，缺少控制场景或确认记录")
    if "待确认" in body:
        raise ValueError("校准报告仍含待确认内容")
    return metadata, selected, evaluation_mode


def _validate_candidates(directory: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for label in CANDIDATE_ORDER:
        path = directory / f"candidate-{label.lower()}.md"
        if not path.is_file():
            raise ValueError(f"缺少匿名候选: {path.name}")
        content = read_text(path)
        if text_units(content) < 200:
            raise ValueError(f"匿名候选正文过短: {path.name}")
        result[label] = {"file": path.name, "sha256": sha256_text(content)}
    return result


def _json_without_duplicate_keys(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"模型评审 JSON 存在重复键: {key}")
            result[key] = value
        return result

    def reject_nonstandard_constant(value: str) -> None:
        raise ValueError(f"模型评审 JSON 禁止非标准数值: {value}")

    if path.stat().st_size > MAX_EVALUATION_BYTES:
        raise ValueError("模型评审 JSON 超过 256 KiB，拒绝解析")
    try:
        payload = json.loads(
            read_text(path),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型评审 JSON 无效: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("模型评审 JSON 顶层必须为对象")
    return payload


def _validate_ranking(value: Any, expected: set[str], label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} ranking 必须为数组")
    ranking = [str(item).strip().upper() for item in value]
    if len(ranking) != len(expected) or set(ranking) != expected:
        expected_text = "、".join(sorted(expected))
        raise ValueError(f"{label} ranking 必须恰好包含 {expected_text}")
    return ranking


def _validate_reviewer(
    value: Any,
    expected_labels: set[str],
    label: str,
    used_evaluator_ids: set[str],
    used_context_ids: set[str],
) -> list[str]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} 必须为对象")
    evaluator_id = str(value.get("evaluator_id") or "")
    context_id = str(value.get("context_id") or "")
    if not is_kebab_id(evaluator_id):
        raise ValueError(f"{label} evaluator_id 必须为 ASCII kebab-case")
    if not is_kebab_id(context_id):
        raise ValueError(f"{label} context_id 必须为 ASCII kebab-case")
    if evaluator_id in used_evaluator_ids:
        raise ValueError(f"模型评审 evaluator_id 重复: {evaluator_id}")
    if context_id in used_context_ids:
        raise ValueError(f"模型评审 context_id 重复: {context_id}")
    required_flags = {
        "isolated_context": True,
        "generated_candidates": False,
        "saw_candidate_sources": False,
        "saw_style_labels": False,
        "saw_model_identity": False,
    }
    for key, expected in required_flags.items():
        if value.get(key) is not expected:
            raise ValueError(f"{label} 必须声明 {key}: {str(expected).lower()}")
    rationale = str(value.get("rationale") or "").strip()
    if text_units(rationale) < 12:
        raise ValueError(f"{label} rationale 过短，无法形成可审计理由")
    ranking = _validate_ranking(value.get("ranking"), expected_labels, label)
    used_evaluator_ids.add(evaluator_id)
    used_context_ids.add(context_id)
    return ranking


def _validate_ai_evaluation(
    path: Path,
    project: str,
    calibration_id: str,
    expected_candidates: dict[str, dict[str, str]],
) -> dict[str, Any]:
    payload = _json_without_duplicate_keys(path)
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError("模型评审 schema_version 必须为 1")
    if payload.get("type") != "style-calibration-evaluation":
        raise ValueError("模型评审 type 必须为 style-calibration-evaluation")
    if payload.get("project") != project:
        raise ValueError("模型评审 project 与当前项目不一致")
    if payload.get("calibration_id") != calibration_id:
        raise ValueError("模型评审 calibration_id 与校准报告不一致")
    if payload.get("blind") is not True:
        raise ValueError("模型评审必须声明 blind: true")
    if payload.get("rubric") != list(RUBRIC):
        raise ValueError("模型评审 rubric 与 Novel Studio 统一量表不一致")

    candidates = payload.get("candidates")
    if not isinstance(candidates, dict) or set(candidates) != CANDIDATE_LABELS:
        raise ValueError("模型评审 candidates 必须恰好包含 A、B、C")
    for candidate_label, expected in expected_candidates.items():
        evidence = candidates.get(candidate_label)
        if not isinstance(evidence, dict):
            raise ValueError(f"模型评审候选 {candidate_label} 证据必须为对象")
        if evidence.get("file") != expected["file"]:
            raise ValueError(f"模型评审候选 {candidate_label} 文件名不匹配")
        digest = str(evidence.get("sha256") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"模型评审候选 {candidate_label} sha256 无效")
        if digest != expected["sha256"]:
            raise ValueError(f"模型评审候选 {candidate_label} 哈希不匹配，样稿可能已变化")

    evaluators = payload.get("evaluators")
    if not isinstance(evaluators, list) or len(evaluators) < 3 or len(evaluators) % 2 == 0:
        raise ValueError("模型评审必须包含至少 3 个且数量为奇数的隔离评审")
    used_evaluator_ids: set[str] = set()
    used_context_ids: set[str] = set()
    scores = {label: 0 for label in CANDIDATE_ORDER}
    for index, evaluator in enumerate(evaluators, start=1):
        ranking = _validate_reviewer(
            evaluator,
            CANDIDATE_LABELS,
            f"评审 {index}",
            used_evaluator_ids,
            used_context_ids,
        )
        for position, candidate_label in enumerate(ranking):
            scores[candidate_label] += BORDA_WEIGHTS[position]

    aggregation = payload.get("aggregation")
    if not isinstance(aggregation, dict):
        raise ValueError("模型评审 aggregation 必须为对象")
    if aggregation.get("method") != "borda-3-2-1":
        raise ValueError("模型评审 aggregation.method 必须为 borda-3-2-1")
    recorded_scores = aggregation.get("scores")
    if not isinstance(recorded_scores, dict) or set(recorded_scores) != CANDIDATE_LABELS:
        raise ValueError("模型评审 aggregation.scores 必须恰好包含 A、B、C")
    for candidate_label, expected_score in scores.items():
        value = recorded_scores.get(candidate_label)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("模型评审 aggregation.scores 必须为整数")
        if value != expected_score:
            raise ValueError("模型评审汇总分数与各评审排序不一致")

    maximum = max(scores.values())
    tied = {label for label, score in scores.items() if score == maximum}
    tie_break = payload.get("tie_break")
    if len(tied) == 1:
        if tie_break not in (None, {}):
            raise ValueError("不存在平票时不得提供 tie_break")
        winner = next(iter(tied))
    else:
        if not isinstance(tie_break, dict):
            raise ValueError("模型评审出现平票，必须提供新的隔离复评")
        eligible = {str(item).strip().upper() for item in as_list(tie_break.get("eligible_candidates"))}
        if eligible != tied:
            raise ValueError("隔离复评 eligible_candidates 必须与平票候选一致")
        ranking = _validate_reviewer(
            tie_break,
            tied,
            "隔离复评",
            used_evaluator_ids,
            used_context_ids,
        )
        winner = ranking[0]
        if str(tie_break.get("winner") or "").strip().upper() != winner:
            raise ValueError("隔离复评 winner 必须等于 ranking 第一名")

    if str(aggregation.get("winner") or "").strip().upper() != winner:
        raise ValueError("模型评审 aggregation.winner 与确定性汇总结果不一致")
    return {
        "winner": winner,
        "scores": scores,
        "evaluator_count": len(evaluators),
        "tie_break_used": len(tied) > 1,
        "sha256": sha256_text(read_text(path)),
    }


def _validate_profile_draft(path: Path, project: str) -> tuple[dict[str, Any], str]:
    metadata, body = parse_document(path)
    if metadata.get("type") != "style-profile":
        raise ValueError("文风草稿 type 必须为 style-profile")
    if metadata.get("project") != project:
        raise ValueError("文风草稿 project 与当前项目不一致")
    if _int(metadata.get("profile-version"), 0) != 1:
        raise ValueError("文风草稿 profile-version 必须为 1")
    if metadata.get("status") != "inactive":
        raise ValueError("文风草稿必须保持 status: inactive，由激活脚本修改")
    for key in (
        "activation-evidence",
        "activation-evidence-sha256",
        "calibration-id",
        "selection-mode",
        "selected-calibration-candidate",
        "calibration-evaluation",
        "calibration-evaluation-sha256",
    ):
        if key in metadata:
            raise ValueError(f"文风草稿不得预置 {key}")
    for placeholder in PLACEHOLDERS:
        if placeholder in body:
            raise ValueError(f"文风草稿仍含占位内容: {placeholder}")
    for heading in REQUIRED_HEADINGS:
        if heading not in body:
            raise ValueError(f"文风草稿缺少章节: {heading}")
    if text_units(body) < 60:
        raise ValueError("文风草稿内容过短，不能形成可执行约束")
    return metadata, body


def _current_profile_state(target: Path, project: str) -> tuple[str, str, dict[str, Any]]:
    if not target.exists():
        return "missing", "missing", {}
    metadata, _ = parse_document(target)
    if metadata.get("type") != "style-profile" or metadata.get("project") != project:
        raise ValueError("现有文风档案类型或 project 不匹配")
    status = str(metadata.get("status") or "")
    if status not in {"inactive", "active"}:
        raise ValueError("现有文风档案 status 必须为 inactive 或 active")
    return status, sha256_text(read_text(target)), metadata


def _activated_text(
    draft_text: str,
    report_relative: str,
    report_sha256: str,
    calibration_id: str,
    selected: str,
    evaluation_mode: str,
    evaluation_relative: str | None,
    evaluation_sha256: str | None,
) -> str:
    normalized = draft_text.replace("\r\n", "\n")
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise ValueError("文风草稿 frontmatter 未闭合")
    header = normalized[4:end]
    body = normalized[end + 5 :]
    lines: list[str] = []
    replaced = False
    for line in header.splitlines():
        if re.fullmatch(r"status:\s*inactive\s*", line):
            lines.extend(
                (
                    "status: active",
                    f"activation-evidence: {json.dumps(report_relative, ensure_ascii=False)}",
                    f"activation-evidence-sha256: {report_sha256}",
                    f"calibration-id: {calibration_id}",
                    f"selection-mode: {evaluation_mode}",
                    f"selected-calibration-candidate: {selected}",
                )
            )
            if evaluation_relative and evaluation_sha256:
                lines.extend(
                    (
                        f"calibration-evaluation: {json.dumps(evaluation_relative, ensure_ascii=False)}",
                        f"calibration-evaluation-sha256: {evaluation_sha256}",
                    )
                )
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        raise ValueError("文风草稿缺少精确的 status: inactive")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def activate(args: argparse.Namespace) -> dict[str, object]:
    root = Path(args.project_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"项目目录不存在: {root}")
    project_meta, _ = parse_document(root / "作品.md")
    project = str(project_meta.get("id") or "")
    if not project:
        raise ValueError("作品.md 缺少项目 id")
    report_root = (root / "报告" / "文风校准").resolve()
    report = ensure_within(report_root, _resolve_project_path(root, args.calibration_report))
    draft = ensure_within(report_root, _resolve_project_path(root, args.profile_draft))
    if report.suffix.lower() != ".md" or draft.suffix.lower() != ".md":
        raise ValueError("校准报告和文风草稿必须为 Markdown")
    if not report.is_file() or not draft.is_file():
        raise ValueError("校准报告或文风草稿不存在")
    if report.parent != draft.parent:
        raise ValueError("校准报告和文风草稿必须位于同一校准目录")

    report_meta, selected, evaluation_mode = _validate_calibration(report, project)
    candidate_evidence = _validate_candidates(report.parent)
    evaluation: dict[str, Any] | None = None
    evaluation_path: Path | None = None
    if evaluation_mode == "ai-panel":
        if not args.evaluation_file:
            raise ValueError("模型评审模式必须传入 --evaluation-file")
        evaluation_path = ensure_within(
            report_root,
            _resolve_project_path(root, args.evaluation_file),
        )
        if evaluation_path.suffix.lower() != ".json" or not evaluation_path.is_file():
            raise ValueError("模型评审文件必须是存在的 JSON 文件")
        if evaluation_path.parent != report.parent:
            raise ValueError("模型评审文件必须与校准报告位于同一目录")
        if evaluation_path.name != str(report_meta.get("evaluation-file")):
            raise ValueError("--evaluation-file 与校准报告声明不一致")
        evaluation = _validate_ai_evaluation(
            evaluation_path,
            project,
            str(report_meta["calibration-id"]),
            candidate_evidence,
        )
        if selected != evaluation["winner"]:
            raise ValueError("校准报告 selected-candidate 与模型评审胜者不一致")
    else:
        if not args.user_confirmed:
            raise ValueError("人工选择模式必须由用户明确确认，并传入 --user-confirmed")
        if args.evaluation_file:
            raise ValueError("人工选择模式不得传入 --evaluation-file")
    draft_meta, _ = _validate_profile_draft(draft, project)
    target = root / "设定" / "文风档案.md"
    current_status, current_hash, current_meta = _current_profile_state(target, project)
    if current_status == "active":
        if _int(draft_meta.get("last-confirmed-chapter"), 0) < _int(
            current_meta.get("last-confirmed-chapter"), 0
        ):
            raise ValueError("重新校准不能降低 last-confirmed-chapter")

    report_relative = report.relative_to(root).as_posix()
    report_sha256 = sha256_text(read_text(report))
    calibration_id = str(report_meta["calibration-id"])
    evaluation_relative = evaluation_path.relative_to(root).as_posix() if evaluation_path else None
    evaluation_sha256 = str(evaluation["sha256"]) if evaluation else None
    proposed = _activated_text(
        read_text(draft),
        report_relative,
        report_sha256,
        calibration_id,
        selected,
        evaluation_mode,
        evaluation_relative,
        evaluation_sha256,
    )
    proposed_hash = sha256_text(proposed)

    if args.apply:
        expected = str(args.expected_current_sha256 or "").lower()
        if not expected:
            raise ValueError("正式写入必须传入预览返回的 --expected-current-sha256")
        if expected != current_hash.lower():
            raise ValueError(f"文风档案已变化，预期 {expected}，当前 {current_hash}")
        _, latest_hash, _ = _current_profile_state(target, project)
        if latest_hash.lower() != expected:
            raise ValueError("文风档案在写入前再次变化，拒绝覆盖")
        if sha256_text(read_text(report)) != report_sha256:
            raise ValueError("校准报告在写入前发生变化，拒绝激活")
        if evaluation_path and evaluation:
            latest_evaluation = _validate_ai_evaluation(
                evaluation_path,
                project,
                calibration_id,
                _validate_candidates(report.parent),
            )
            if (
                latest_evaluation["sha256"] != evaluation_sha256
                or latest_evaluation["winner"] != selected
            ):
                raise ValueError("模型评审证据在写入前发生变化，拒绝激活")
        atomic_write_text(target, proposed)
        applied_meta, _ = parse_document(target)
        if applied_meta.get("status") != "active" or sha256_text(read_text(target)) != proposed_hash:
            raise ValueError("文风档案写入后验证失败")

    return {
        "ok": True,
        "mode": "applied" if args.apply else "preview",
        "project_root": str(root),
        "target": str(target),
        "calibration_id": calibration_id,
        "evaluation_mode": evaluation_mode,
        "evaluation_file": str(evaluation_path) if evaluation_path else None,
        "evaluation_sha256": evaluation_sha256,
        "evaluation_scores": evaluation["scores"] if evaluation else None,
        "evaluator_count": evaluation["evaluator_count"] if evaluation else None,
        "tie_break_used": evaluation["tie_break_used"] if evaluation else None,
        "selected_candidate": selected,
        "current_profile_status": current_status,
        "current_profile_sha256": current_hash,
        "proposed_profile_sha256": proposed_hash,
        "applied": bool(args.apply),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="预览或激活模型盲评或用户确认的单书文风档案")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--calibration-report", required=True)
    parser.add_argument("--profile-draft", required=True)
    parser.add_argument("--evaluation-file")
    parser.add_argument("--user-confirmed", action="store_true", help="仅用于人工选择兼容模式")
    parser.add_argument("--expected-current-sha256")
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = activate(args)
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
