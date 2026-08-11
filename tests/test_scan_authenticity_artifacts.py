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
SCANNER = SCRIPT_ROOT / "scan_authenticity_artifacts.py"
PYTHON = sys.executable


def run_scanner(*args: object, expect: int = 0) -> dict[str, object]:
    result = subprocess.run(
        [PYTHON, str(SCANNER), *(str(arg) for arg in args), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if result.returncode != expect:
        raise AssertionError(f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return json.loads(result.stdout)


def digest(root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda p: p.as_posix()):
        value.update(path.relative_to(root).as_posix().encode("utf-8"))
        value.update(path.read_bytes())
    return value.hexdigest()


def categories(chapter: dict[str, object]) -> set[str]:
    return {item["category"] for item in chapter["findings"]}


class AuthenticityArtifactScannerTests(unittest.TestCase):
    def test_skill_routes_authenticity_workflow_and_records_source_boundary(self) -> None:
        skill_root = SCRIPT_ROOT.parent
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        workflow = (skill_root / "references/authenticity-revision.md").read_text(encoding="utf-8")
        sources = (skill_root / "references/method-sources.md").read_text(encoding="utf-8")
        self.assertIn("references/authenticity-revision.md", skill)
        self.assertIn("scan_authenticity_artifacts.py", skill)
        self.assertIn("不判断文本来源", workflow)
        self.assertIn("首次读者不得被“找 AI 味”的预设污染", workflow)
        self.assertIn("未复制其 JavaScript 规则", sources)

    def test_reports_workflow_leak_and_review_candidates_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            chapter = root / "第1章.md"
            chapter.write_text(
                """---
type: chapter
number: 1
---

# 第一章 雨夜

下面是根据你的要求修改后的章节：

他不是害怕，而是在衡量。她并非不懂，而是不愿接话。问题不在输赢，而在谁先开口。这意味着真正的问题在于选择、责任、秩序和边界。

流程已经确认，方案进入执行，数据和反馈都被记录下来。

她呼吸一滞。他的指节泛白。老周扯了扯嘴角。

谁也不知道，这才刚刚开始。
""",
                encoding="utf-8",
            )
            before = digest(root)
            payload = run_scanner("--project-root", root)
            self.assertEqual(before, digest(root))
            self.assertTrue(payload["read_only"])
            self.assertEqual(payload["summary"]["blocking_findings"], 1)
            found = categories(payload["chapters"][0])
            self.assertIn("workflow-leak", found)
            self.assertIn("contrast-template", found)
            self.assertIn("explanatory-bridge", found)
            self.assertIn("abstract-cluster", found)
            self.assertIn("procedural-cluster", found)
            self.assertIn("micro-action-density", found)
            self.assertIn("trailer-ending", found)

    def test_remaining_review_categories_have_positive_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "第4章.md").write_text(
                "# 第四章\n\n那不是风，不是雨，而是有人在门外用指甲刮木板。\n",
                encoding="utf-8",
            )
            (root / "第5章.md").write_text(
                "# 第五章\n\n风像刀刮过窗纸，钟声仿佛潮水漫进屋里，脚步如同碎冰压上台阶。\n",
                encoding="utf-8",
            )
            (root / "第6章.md").write_text(
                "# 第六章\n\n灯熄了。说到底，这一夜留下的是她没有带走的钥匙。\n",
                encoding="utf-8",
            )
            payload = run_scanner(root)
            found = {category for chapter in payload["chapters"] for category in categories(chapter)}
            self.assertIn("negation-parade", found)
            self.assertIn("simile-cluster", found)
            self.assertIn("verdict-ending", found)

    def test_legitimate_dialogue_dash_and_metafiction_are_never_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            chapter = Path(temp) / "第2章.md"
            chapter.write_text(
                """# 第二章

“不是你错，而是我没说清。”她把信纸折好——沿着昨天留下的折痕。

屏幕里的角色说：“作为AI，我也有拒绝的权利。”

“老规矩。”老周说。过了会儿，他又敲了敲门：“老规矩。”

交接时间是五点三十九，真正开盒是六点四十八。
""",
                encoding="utf-8",
            )
            payload = run_scanner(chapter)
            item = payload["chapters"][0]
            self.assertEqual(item["blocking_findings"], 0)
            self.assertNotIn("contrast-template", categories(item))
            self.assertNotIn("em-dash", categories(item))
            self.assertNotIn("verdict-ending", categories(item))

    def test_micro_actions_require_density_and_normal_prose_can_be_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            chapter = Path(temp) / "第3章.md"
            chapter.write_text(
                """# 第三章

雨从棚沿落下来。小满把最后一份饭递过去，手在纸袋底下多托了一秒。

对方呼吸一滞，却没有马上接。她等着，没有替他决定。
""",
                encoding="utf-8",
            )
            payload = run_scanner(chapter)
            self.assertNotIn("micro-action-density", categories(payload["chapters"][0]))
            self.assertEqual(payload["summary"]["blocking_findings"], 0)

    def test_embedded_chapters_and_chinese_number_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            book = Path(temp) / "合集.md"
            book.write_text(
                """---
number: 99
---

# 第一章 开门

门开了。

# 第二章 复核

流程、规则、数据和指标都需要确认。
""",
                encoding="utf-8",
            )
            payload = run_scanner(book, "--chapter", 2)
            self.assertEqual(len(payload["chapters"]), 1)
            self.assertTrue(payload["chapters"][0]["title"].startswith("第二章"))
            self.assertIn("procedural-cluster", categories(payload["chapters"][0]))

    def test_chapter_production_metadata_combinations_block_without_ordinary_word_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            leaking = root / "第18章.md"
            leaking.write_text(
                """# 第十八章 终稿

status: accepted
字段: 审查状态
控制卡: 候选稿
""",
                encoding="utf-8",
            )
            payload = run_scanner(leaking)
            item = payload["chapters"][0]
            self.assertEqual(item["blocking_findings"], 1)
            workflow = [finding for finding in item["findings"] if finding["category"] == "workflow-leak"]
            self.assertTrue(workflow)
            matched = set(workflow[0]["evidence"][0]["matched_terms"])
            self.assertIn("accepted", matched)

            sword = root / "剑息.md"
            sword.write_text("十八章比赛中的剑息字段：候选值。\n", encoding="utf-8")
            sword_payload = run_scanner(sword)
            self.assertEqual(sword_payload["summary"]["blocking_findings"], 1)
            sword_workflow = [
                finding
                for finding in sword_payload["chapters"][0]["findings"]
                if finding["category"] == "workflow-leak"
            ]
            self.assertIn("字段", sword_workflow[0]["evidence"][0]["matched_terms"])

            all_terms = root / "第20章-元数据.md"
            all_terms.write_text(
                "十八章字段: x 台账: x accepted 候选: x 审查: x 控制卡: x\n",
                encoding="utf-8",
            )
            all_terms_payload = run_scanner(all_terms)
            all_term_findings = [
                finding
                for finding in all_terms_payload["chapters"][0]["findings"]
                if finding["category"] == "workflow-leak"
            ]
            self.assertEqual(all_terms_payload["summary"]["blocking_findings"], 1)
            self.assertTrue(
                {"字段", "台账", "accepted", "候选", "审查", "控制卡"}.issubset(
                    set(all_term_findings[0]["evidence"][0]["matched_terms"])
                )
            )

            ordinary = root / "第十九章.md"
            ordinary.write_text(
                """# 第十九章 交班

今天审查控制卡，候选方案由现场决定，台账放在柜里。
""",
                encoding="utf-8",
            )
            ordinary_payload = run_scanner(ordinary)
            self.assertEqual(ordinary_payload["summary"]["blocking_findings"], 0)

            ordinary_field = root / "普通字段.md"
            ordinary_field.write_text("字段：姓名\n", encoding="utf-8")
            ordinary_field_payload = run_scanner(ordinary_field)
            self.assertEqual(ordinary_field_payload["summary"]["blocking_findings"], 0)

    def test_fail_on_blocking_invalid_utf8_and_no_files_have_defined_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            leaking = root / "第1章.md"
            leaking.write_text("修改说明：删除重复句。\n\n正文。", encoding="utf-8")
            payload = run_scanner(leaking, "--fail-on-blocking", expect=1)
            self.assertEqual(payload["summary"]["blocking_findings"], 1)

            invalid = root / "第2章.md"
            invalid.write_bytes(b"\xff\xfe\x00broken\n\xe4\xbd\xa0")
            invalid_payload = run_scanner(invalid)
            self.assertTrue(any("UTF-8 解码失败" in item for item in invalid_payload["warnings"]))

            empty = root / "empty"
            empty.mkdir()
            empty_payload = run_scanner(empty)
            self.assertTrue(empty_payload["ok"])
            self.assertEqual(empty_payload["chapters"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
