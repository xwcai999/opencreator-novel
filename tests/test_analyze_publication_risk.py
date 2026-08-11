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
ANALYZER = SCRIPT_ROOT / "analyze_publication_risk.py"
PYTHON = sys.executable


def run_analyzer(root: Path, *args: object) -> dict[str, object]:
    result = subprocess.run(
        [PYTHON, str(ANALYZER), "--project-root", str(root), *(str(arg) for arg in args), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode != 0:
        raise AssertionError(f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return json.loads(result.stdout)


def digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        value.update(path.relative_to(root).as_posix().encode("utf-8"))
        value.update(path.read_bytes())
    return value.hexdigest()


class PublicationRiskAnalyzerTests(unittest.TestCase):
    def test_three_failed_books_locate_known_cross_chapter_risks_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            # 失败作品一：承诺锚点只在前后章节出现，中间章疑似冷线。
            anchor_book = root / "失败作品-锚点断裂"
            anchor_book.mkdir()
            (anchor_book / "第1章.md").write_text("# 第一章\n\n主线锚点出现，订单已经下达。", encoding="utf-8")
            (anchor_book / "第2章.md").write_text("# 第二章\n\n人物去仓库取工具。", encoding="utf-8")
            (anchor_book / "第3章.md").write_text("# 第三章\n\n主线锚点再次出现，订单进入交付。", encoding="utf-8")
            before_anchor = digest(anchor_book)
            anchor_payload = run_analyzer(anchor_book, "--anchor", "主线锚点")
            self.assertEqual(before_anchor, digest(anchor_book))
            anchor_candidates = anchor_payload["publication_risk"]["target_anchor_missing_candidates"]
            self.assertEqual([item["chapter"] for item in anchor_candidates], [2])

            # 失败作品二：每章都走同一套目标—阻力—流程—收束，并在章末叠加总结。
            process_book = root / "失败作品-流程同构"
            process_book.mkdir()
            body = "\n".join(
                [
                    "目标订单已经确认。问题偏差导致设备停机。流程方案步骤需要复核、记录、表格、试验、节点、调整和确认。",
                    "目标订单已经确认。问题偏差导致设备停机。流程方案步骤需要复核、记录、表格、试验、节点、调整和确认。",
                    "任务完成并通过签字，大家终于明白这一步的意义，下一步继续。",
                ]
                * 8
            )
            for index in range(1, 4):
                (process_book / f"第{index:03d}章.md").write_text(
                    f"# 第{index}章\n\n{body}\n\n任务完成。大家终于明白。下一步继续。",
                    encoding="utf-8",
                )
            process_payload = run_analyzer(process_book)
            risk = process_payload["publication_risk"]
            self.assertGreaterEqual(len(risk["process_density"]["candidates"]), 3)
            self.assertGreaterEqual(len(risk["chapter_end_multiple_closures"]), 3)
            self.assertTrue(risk["repeated_structures"]["groups"])

            # 失败作品三：人物对白可抽取，但需要匿名后做声线盲测。
            voice_book = root / "失败作品-声线同质"
            voice_book.mkdir()
            for index in range(1, 4):
                (voice_book / f"第{index:03d}章.md").write_text(
                    f"# 第{index}章\n\n"
                    "林峥说：“先把数据记下来，不要急着下结论。”\n\n"
                    "秦守成问：“先把数据记下来，下一步再决定。”\n\n"
                    "许珊回答：“先把数据记下来，边界确认后再继续。”\n",
                    encoding="utf-8",
                )
            voice_payload = run_analyzer(voice_book)
            voice = voice_payload["publication_risk"]["voice_blind_test_inputs"]
            self.assertGreaterEqual(len(voice), 4)
            self.assertGreaterEqual(voice_payload["publication_risk"]["voice_blind_test_summary"]["speaker_count"], 2)
            self.assertTrue(all("林峥" not in item["text"] for item in voice))

    def test_empty_input_keeps_read_only_evidence_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = run_analyzer(Path(temp))
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["read_only"])
            self.assertEqual(payload["chapters"], 0)
            self.assertTrue(payload["warnings"])
            self.assertIn("文学", payload["interpretation"])
            self.assertIn("回读候选", payload["interpretation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
