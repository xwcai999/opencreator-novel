from __future__ import annotations

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
    result = subprocess.run(
        [PYTHON, str(SCRIPT_ROOT / name), *(str(arg) for arg in args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode != expect:
        raise AssertionError(f"return={result.returncode} expected={expect}\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def ledger(project_id: str, rows: str, *, version: bool = True) -> str:
    version_lines = "ledger-version: 2\ntracking-start-chapter: 1\ncold-after-chapters: 8\n" if version else ""
    return f"""---
type: expectation-ledger
project: {project_id}
{version_lines}---

# 待兑现项

| ID | 类型 | 承诺 | 状态 | 首次出现 | 最近推进 | 兑现窗口 | 正文证据 | 禁止提前揭露 | 所属驱动 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{rows}"""


class ExpectationLedgerTests(unittest.TestCase):
    def init_project(self, root: Path) -> str:
        payload = run_script(
            "init_project.py", "--project-root", root, "--title", "伏笔测试书",
            "--scope", "medium", "--complexity", "standard", "--primary-driver", "information"
        )
        self.assertTrue(payload["ok"])
        work = (root / "作品.md").read_text(encoding="utf-8")
        project_id = next(line.split(":", 1)[1].strip() for line in work.splitlines() if line.startswith("id:"))
        return project_id

    def test_new_template_uses_v2_and_empty_ledger_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            self.init_project(root)
            text = (root / "状态/待兑现.md").read_text(encoding="utf-8")
            self.assertIn("ledger-version: 2", text)
            result = run_script("validate_project.py", "--project-root", root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["counts"]["expectations"], 0)

    def test_long_hook_cannot_be_fulfilled_by_planting_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project_id = self.init_project(root)
            rows = "| clue-mother | 长钩 | 母亲旧钉真相 | fulfilled | 第001章 | 第001章 | 终局 | 第001章首次出现旧钉 | 第20章前不得确认母亲存活 | information |\n"
            write(root / "状态/待兑现.md", ledger(project_id, rows))
            result = run_script("validate_project.py", "--project-root", root, expect=1)
            self.assertTrue(any("最终兑现" in item for item in result["errors"]))

    def test_overdue_nonterminal_item_blocks_next_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project_id = self.init_project(root)
            rows = "| clue-tax | 悬疑 | 隐藏免税通道 | planned | 未出现 | 未出现 | 第001章 | 尚未进入正文 | 第001章前不得揭示 | information |\n"
            write(root / "状态/待兑现.md", ledger(project_id, rows))
            result = run_script("expectation_ledger.py", "--project-root", root, "--target-chapter", 2, expect=1)
            self.assertEqual(result["overdue"], ["clue-tax"])

    def test_context_always_injects_active_old_line_for_unrelated_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project_id = self.init_project(root)
            rows = "| clue-old-bell | 伏笔 | 旧钟背面的名字 | planted | 第001章 | 第001章 | 第010—012章 | 第001章出现无名刻痕 | 第10章前不得解释名字 | information |\n"
            write(root / "状态/待兑现.md", ledger(project_id, rows))
            output = root / "索引/context-pack-2.md"
            result = run_script(
                "build_context_pack.py", "--project-root", root, "--chapter", 2,
                "--query", "两人在厨房吃早饭", "--output", output
            )
            text = output.read_text(encoding="utf-8")
            self.assertIn("clue-old-bell", text)
            self.assertIn("状态/待兑现.md", result["included"])
            self.assertEqual(result["included"].count("状态/待兑现.md"), 1)
            self.assertNotIn("来源：状态/待兑现.md", text)
            self.assertLess(text.index("强制连续性"), text.index("来源：作品.md"))

    def test_legacy_ledger_remains_compatible_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project_id = self.init_project(root)
            write(root / "状态/待兑现.md", ledger(project_id, "", version=False))
            result = run_script("validate_project.py", "--project-root", root)
            self.assertTrue(result["ok"])
            self.assertTrue(any("旧版自由文本台账" in item for item in result["warnings"]))

    def test_v2_outline_requires_valid_expectation_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            project_id = self.init_project(root)
            rows = "| clue-old-bell | 伏笔 | 旧钟名字 | planted | 第001章 | 第001章 | 第010章 | 第001章出现刻痕 | 第10章前不得揭名 | information |\n"
            write(root / "状态/待兑现.md", ledger(project_id, rows))
            outline = root / "大纲/细纲/第1章.md"
            write(outline, """---
type: chapter-outline
id: chapter-outline-001
number: 1
title: 起钟
expectations-advanced: [clue-missing]
expectations-fulfilled: []
---

# 第一章细纲
""")
            result = run_script("validate_project.py", "--project-root", root, expect=1)
            self.assertTrue(any("expectations-forbidden" in item for item in result["errors"]))
            self.assertTrue(any("continuity-sources" in item for item in result["errors"]))
            self.assertTrue(any("clue-missing" in item for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
