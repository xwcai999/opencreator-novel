from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "novel-studio-skill" / "skills" / "novel-studio" / "scripts"
PYTHON = sys.executable


def run_script(name: str, *args: object, expect: int = 0) -> dict[str, object]:
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [PYTHON, str(SCRIPT_ROOT / name), *(str(arg) for arg in args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env=environment,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"返回码 {result.returncode}，预期 {expect}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return json.loads(result.stdout)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


class StyleCalibrationTests(unittest.TestCase):
    def initialize(self, root: Path) -> str:
        payload = run_script(
            "init_project.py",
            "--project-root",
            root,
            "--title",
            "雨夜车站",
            "--scope",
            "medium",
            "--complexity",
            "standard",
            "--primary-driver",
            "relationship",
        )
        return str(payload["project_id"])

    def calibration_files(
        self,
        root: Path,
        project: str,
        calibration_id: str = "style-calibration-001",
        selected: str = "A",
        mix_sources: str = "[]",
        last_chapter: int = 0,
    ) -> tuple[Path, Path]:
        directory = root / "报告/文风校准" / calibration_id
        candidate = "雨水敲着铁皮棚顶。林岚没有看周野，只把车票沿折痕慢慢压平。" * 12
        for label in ("a", "b", "c"):
            write(directory / f"candidate-{label}.md", candidate + label.upper())
        report = directory / "calibration-report.md"
        write(
            report,
            f"""---
type: style-calibration
project: {project}
calibration-id: {calibration_id}
status: confirmed
blind-labels: true
candidates: [A, B, C]
selected-candidate: {selected}
mix-sources: {mix_sources}
---

# 单书文风校准

控制场景固定为雨夜车站重逢。三份候选使用同一视角、人物目标、动作、信息边界和结束节点。

用户在不知道模型、生成顺序和风格说明的情况下完成选择，并明确允许据此激活本书文风档案。
""",
        )
        draft = directory / "profile-draft.md"
        write(
            draft,
            f"""---
type: style-profile
project: {project}
profile-version: 1
status: inactive
source-policy: user-confirmed-or-accepted
writer-consistency-scope: volume
model-policy: adaptive
last-confirmed-chapter: {last_chapter}
---

# 文风档案

## 叙事声音

- 使用贴近人物但不直接解释情绪的第三人称限知。
- 句子以中短句为主，在情绪停顿处保留较长的环境句。

## 场景表达

- 关系变化通过动作迟疑、物件交接和未说完的话呈现。
- 环境细节只选择会改变人物身体感受或决定的部分。

## 稳定偏好

- 保留克制但清晰的情绪余波，以及对话中的立场差异。
- 避免结论先行、替人物总结感受和连续使用相同句式。

## 人物声音边界

人物专属措辞继续记录在角色文件，本档案只约束全书共同叙事声音。
""",
        )
        return report, draft

    def ai_calibration_files(
        self,
        root: Path,
        project: str,
        calibration_id: str = "style-calibration-ai-001",
        selected: str = "A",
        rankings: list[list[str]] | None = None,
        tie_break: dict[str, object] | None = None,
    ) -> tuple[Path, Path, Path]:
        report, draft = self.calibration_files(
            root,
            project,
            calibration_id=calibration_id,
            selected=selected,
        )
        write(
            report,
            f"""---
type: style-calibration
project: {project}
calibration-id: {calibration_id}
status: evaluated
evaluation-mode: ai-panel
blind-labels: true
candidates: [A, B, C]
selected-candidate: {selected}
mix-sources: []
evaluation-file: panel-evaluation.json
---

# 单书文风校准

控制场景固定为雨夜车站重逢。三份候选使用同一视角、人物目标、动作、信息边界和结束节点。

三个隔离模型上下文在看不到来源、风格标签和模型身份的情况下完成排序；结果只代表模型评审，不代表真实市场数据。
""",
        )
        rankings = rankings or [
            ["A", "B", "C"],
            ["B", "A", "C"],
            ["A", "C", "B"],
        ]
        scores = {label: 0 for label in ("A", "B", "C")}
        for ranking in rankings:
            for position, label in enumerate(ranking):
                scores[label] += (3, 2, 1)[position]
        maximum = max(scores.values())
        leaders = [label for label, score in scores.items() if score == maximum]
        winner = leaders[0] if len(leaders) == 1 else str((tie_break or {}).get("winner") or selected)
        evaluators: list[dict[str, object]] = []
        for index, ranking in enumerate(rankings, start=1):
            evaluators.append(
                {
                    "evaluator_id": f"reviewer-{index:03d}",
                    "context_id": f"context-{index:03d}",
                    "isolated_context": True,
                    "generated_candidates": False,
                    "saw_candidate_sources": False,
                    "saw_style_labels": False,
                    "saw_model_identity": False,
                    "ranking": ranking,
                    "rationale": "该候选更贴合目标读者，声音清楚，并且能够支撑跨章节变化。",
                }
            )
        candidates: dict[str, dict[str, str]] = {}
        for label in ("A", "B", "C"):
            candidate_path = report.parent / f"candidate-{label.lower()}.md"
            content = candidate_path.read_text(encoding="utf-8")
            candidates[label] = {
                "file": candidate_path.name,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        evaluation = report.parent / "panel-evaluation.json"
        write(
            evaluation,
            json.dumps(
                {
                    "schema_version": 1,
                    "type": "style-calibration-evaluation",
                    "project": project,
                    "calibration_id": calibration_id,
                    "blind": True,
                    "rubric": [
                        "target-reader-fit",
                        "voice-distinctiveness",
                        "cross-chapter-sustainability",
                        "character-elasticity",
                        "ai-artifact-risk",
                    ],
                    "candidates": candidates,
                    "evaluators": evaluators,
                    "aggregation": {
                        "method": "borda-3-2-1",
                        "scores": scores,
                        "winner": winner,
                    },
                    "tie_break": tie_break,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        return report, draft, evaluation

    def test_ai_panel_preview_then_apply_without_user_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            report, draft, evaluation = self.ai_calibration_files(root, project)
            target = root / "设定/文风档案.md"
            before = target.read_bytes()

            preview = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
            )
            self.assertEqual(preview["mode"], "preview")
            self.assertEqual(preview["evaluation_mode"], "ai-panel")
            self.assertEqual(preview["selected_candidate"], "A")
            self.assertEqual(preview["evaluator_count"], 3)
            self.assertFalse(preview["tie_break_used"])
            self.assertEqual(before, target.read_bytes())

            applied = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
                "--expected-current-sha256",
                preview["current_profile_sha256"],
                "--apply",
            )
            self.assertTrue(applied["applied"])
            active_text = target.read_text(encoding="utf-8")
            self.assertIn("selection-mode: ai-panel", active_text)
            self.assertIn("calibration-evaluation:", active_text)
            self.assertIn("calibration-evaluation-sha256:", active_text)

    def test_ai_panel_rejects_candidate_changed_after_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            report, draft, evaluation = self.ai_calibration_files(root, project)
            candidate = report.parent / "candidate-a.md"
            write(candidate, candidate.read_text(encoding="utf-8") + "样稿评审后被替换。")

            result = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
                expect=1,
            )
            self.assertIn("哈希不匹配", result["error"])

    def test_ai_panel_rejects_duplicate_or_nonisolated_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            report, draft, evaluation = self.ai_calibration_files(root, project)
            original = json.loads(evaluation.read_text(encoding="utf-8"))

            duplicate = json.loads(json.dumps(original))
            duplicate["evaluators"][1]["context_id"] = duplicate["evaluators"][0]["context_id"]
            write(evaluation, json.dumps(duplicate, ensure_ascii=False, indent=2) + "\n")
            duplicate_result = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
                expect=1,
            )
            self.assertIn("context_id 重复", duplicate_result["error"])

            nonisolated = json.loads(json.dumps(original))
            nonisolated["evaluators"][0]["isolated_context"] = False
            write(evaluation, json.dumps(nonisolated, ensure_ascii=False, indent=2) + "\n")
            nonisolated_result = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
                expect=1,
            )
            self.assertIn("isolated_context: true", nonisolated_result["error"])

    def test_ai_panel_rejects_report_winner_not_computed_by_panel(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            report, draft, evaluation = self.ai_calibration_files(root, project, selected="B")
            result = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
                expect=1,
            )
            self.assertIn("selected-candidate 与模型评审胜者不一致", result["error"])

    def test_ai_panel_tie_requires_fresh_isolated_tiebreak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            rankings = [["A", "B", "C"], ["B", "C", "A"], ["C", "A", "B"]]
            report, draft, evaluation = self.ai_calibration_files(
                root,
                project,
                selected="C",
                rankings=rankings,
            )
            missing = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
                expect=1,
            )
            self.assertIn("出现平票", missing["error"])

            payload = json.loads(evaluation.read_text(encoding="utf-8"))
            payload["aggregation"]["winner"] = "C"
            payload["tie_break"] = {
                "evaluator_id": "reviewer-004",
                "context_id": "context-004",
                "isolated_context": True,
                "generated_candidates": False,
                "saw_candidate_sources": False,
                "saw_style_labels": False,
                "saw_model_identity": False,
                "eligible_candidates": ["A", "B", "C"],
                "ranking": ["C", "A", "B"],
                "winner": "C",
                "rationale": "复评只比较平票候选，C 的长期稳定性和人物承载力更好。",
            }
            write(evaluation, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            preview = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--evaluation-file",
                evaluation,
                "--profile-draft",
                draft,
            )
            self.assertEqual(preview["selected_candidate"], "C")
            self.assertTrue(preview["tie_break_used"])

    def test_preview_then_apply_and_reject_stale_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            report, draft = self.calibration_files(root, project)
            target = root / "设定/文风档案.md"
            before = target.read_bytes()

            preview = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
            )
            self.assertEqual(preview["mode"], "preview")
            self.assertFalse(preview["applied"])
            self.assertEqual(before, target.read_bytes())

            applied = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
                "--expected-current-sha256",
                preview["current_profile_sha256"],
                "--apply",
            )
            self.assertTrue(applied["applied"])
            active_text = target.read_text(encoding="utf-8")
            self.assertIn("status: active", active_text)
            self.assertIn("selected-calibration-candidate: A", active_text)
            self.assertIn("activation-evidence:", active_text)

            stale = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
                "--expected-current-sha256",
                preview["current_profile_sha256"],
                "--apply",
                expect=1,
            )
            self.assertFalse(stale["ok"])
            self.assertIn("已变化", stale["error"])

            report2, draft2 = self.calibration_files(
                root,
                project,
                calibration_id="style-calibration-002",
                selected="B",
                last_chapter=3,
            )
            preview2 = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report2,
                "--profile-draft",
                draft2,
                "--user-confirmed",
            )
            reapplied = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report2,
                "--profile-draft",
                draft2,
                "--user-confirmed",
                "--expected-current-sha256",
                preview2["current_profile_sha256"],
                "--apply",
            )
            self.assertEqual(reapplied["selected_candidate"], "B")
            recalibrated_text = target.read_text(encoding="utf-8")
            self.assertIn("calibration-id: style-calibration-002", recalibrated_text)
            self.assertIn("last-confirmed-chapter: 3", recalibrated_text)

            context = run_script(
                "build_context_pack.py",
                "--project-root",
                root,
                "--query",
                "雨夜关系变化",
                "--output",
                root / "索引/context-pack-style.md",
            )
            self.assertIn("设定/文风档案.md", context["included"])

    def test_requires_confirmation_and_complete_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            report, draft = self.calibration_files(root, project)
            target = root / "设定/文风档案.md"
            before = target.read_bytes()

            unconfirmed = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                expect=1,
            )
            self.assertIn("用户明确确认", unconfirmed["error"])
            write(draft, draft.read_text(encoding="utf-8").replace("避免结论先行", "待确认"))
            placeholder = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
                expect=1,
            )
            self.assertIn("占位内容", placeholder["error"])
            self.assertEqual(before, target.read_bytes())

    def test_rejects_project_mismatch_and_missing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            report, draft = self.calibration_files(root, project)
            original_report = report.read_text(encoding="utf-8")
            write(report, original_report.replace(f"project: {project}", "project: book-wrong"))
            mismatch = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
                expect=1,
            )
            self.assertIn("project 与当前项目不一致", mismatch["error"])

            write(report, original_report)
            (report.parent / "candidate-c.md").unlink()
            missing = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
                expect=1,
            )
            self.assertIn("缺少匿名候选", missing["error"])

    def test_old_project_without_profile_and_mixed_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project = self.initialize(root)
            (root / "设定/文风档案.md").unlink()
            report, draft = self.calibration_files(
                root,
                project,
                selected="mixed",
                mix_sources="[A, C]",
            )
            preview = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
            )
            self.assertEqual(preview["current_profile_sha256"], "missing")
            applied = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                report,
                "--profile-draft",
                draft,
                "--user-confirmed",
                "--expected-current-sha256",
                "missing",
                "--apply",
            )
            self.assertEqual(applied["selected_candidate"], "MIXED")
            self.assertTrue((root / "设定/文风档案.md").is_file())

            outside = Path(temp) / "outside.md"
            write(outside, report.read_text(encoding="utf-8"))
            escaped = run_script(
                "activate_style_profile.py",
                "--project-root",
                root,
                "--calibration-report",
                outside,
                "--profile-draft",
                draft,
                "--user-confirmed",
                expect=1,
            )
            self.assertIn("路径越界", escaped["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
