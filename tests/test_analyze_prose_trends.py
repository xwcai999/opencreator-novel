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
ANALYZER = SCRIPT_ROOT / "analyze_prose_trends.py"
PYTHON = sys.executable


def run_analyzer(*args: object) -> dict[str, object]:
    result = subprocess.run(
        [PYTHON, str(ANALYZER), *(str(arg) for arg in args), "--json"],
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


class AnalyzeProseTrendTests(unittest.TestCase):
    def test_chinese_dialogue_rhythm_patterns_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            chapter = root / "第1章.md"
            chapter.write_text(
                """---
type: chapter
number: 1
---

# 第一章

“你还送吗？”乔麦问。

老周把雨衣折好。“送。不是为了指标，而是那户人还在等。”

流程已经复核，状态也有记录。这意味着他们可以出发。
""",
                encoding="utf-8",
            )
            before = digest(root)
            payload = run_analyzer("--project-root", root)
            after = digest(root)
            self.assertEqual(before, after)
            self.assertTrue(payload["read_only"])
            self.assertEqual(len(payload["chapters"]), 1)
            item = payload["chapters"][0]
            self.assertGreater(item["dialogue"]["ratio"], 0)
            self.assertIn("不是_而是", item["repeated_structures"]["pattern_counts"])
            self.assertGreater(item["process_language"]["count"], 0)

    def test_empty_short_mixed_language_and_invalid_utf8_have_defined_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "第1章.md").write_text("", encoding="utf-8")
            (root / "第2章.md").write_text('He said, "Wait."\n\n她点头。', encoding="utf-8")
            (root / "第3章.md").write_bytes(b"\xff\xfe\x00broken\n\xe4\xbd\xa0")
            payload = run_analyzer(root)
            self.assertEqual(len(payload["chapters"]), 3)
            self.assertTrue(any("为空" in warning for warning in payload["chapters"][0]["warnings"]))
            self.assertGreaterEqual(payload["chapters"][1]["dialogue"]["turns"], 1)
            self.assertTrue(any("UTF-8 解码失败" in warning for warning in payload["warnings"]))

    def test_embedded_chapters_and_cross_chapter_trend(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "合集.md"
            path.write_text(
                """# 第一章 开门

“来了？”她问。“来了。”他说。

门开了。

# 第二章 复核

流程需要复核。规则需要确认。数据需要记录。

这不是结束，而是新的开始。
""",
                encoding="utf-8",
            )
            payload = run_analyzer(path, "--window-size", 1)
            self.assertEqual(len(payload["chapters"]), 2)
            self.assertEqual(len(payload["windows"]), 2)
            self.assertGreater(
                payload["windows"][0]["dialogue_ratio_mean"],
                payload["windows"][1]["dialogue_ratio_mean"],
            )
            self.assertGreater(
                payload["windows"][1]["process_per_1000_mean"],
                payload["windows"][0]["process_per_1000_mean"],
            )

    def test_no_files_returns_evidence_payload_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = run_analyzer(temp)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["chapters"], [])
            self.assertTrue(payload["warnings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
