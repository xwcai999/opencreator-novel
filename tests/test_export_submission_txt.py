from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "novel-studio-skill" / "skills" / "novel-studio" / "scripts" / "export_submission_txt.py"


def chapter(number: int, title: str, body: str, *, heading: str = "", status: str = "accepted") -> str:
    heading_text = f"{heading}\n\n" if heading else ""
    return (
        "---\n"
        "type: chapter\n"
        f"id: chapter-{number:03d}\n"
        f"number: {number}\n"
        f"title: {title}\n"
        f"status: {status}\n"
        "---\n\n"
        f"{heading_text}{body}\n"
    )


class ExportSubmissionTxtTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "正文").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_export(self, expect: int = 0) -> dict[str, object]:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(self.root), "--output", "投稿/蛙蛙/book.txt", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=30,
        )
        self.assertEqual(result.returncode, expect, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_exports_frontmatter_titles_without_duplicate_markdown_headings(self) -> None:
        (self.root / "正文/第001章.md").write_text(chapter(1, "开门", "第一段。", heading="# 第1章 开门"), encoding="utf-8")
        (self.root / "正文/第002章.md").write_text(chapter(2, "来客", "第二段。"), encoding="utf-8")
        result = self.run_export()
        self.assertTrue(result["ok"])
        data = (self.root / "投稿/蛙蛙/book.txt").read_bytes()
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        text = data.decode("utf-8")
        self.assertEqual(text.count("第1章 开门"), 1)
        self.assertEqual(text.count("第2章 来客"), 1)
        self.assertNotIn("#", text)
        self.assertNotIn("---", text)

    def test_rejects_gaps_and_does_not_write_partial_output(self) -> None:
        (self.root / "正文/第001章.md").write_text(chapter(1, "开门", "第一段。"), encoding="utf-8")
        (self.root / "正文/第003章.md").write_text(chapter(3, "散席", "第三段。"), encoding="utf-8")
        result = self.run_export(expect=1)
        self.assertFalse(result["ok"])
        self.assertFalse((self.root / "投稿/蛙蛙/book.txt").exists())

    def test_rejects_unaccepted_chapter(self) -> None:
        (self.root / "正文/第001章.md").write_text(chapter(1, "开门", "第一段。", status="draft"), encoding="utf-8")
        result = self.run_export(expect=1)
        self.assertIn("status=accepted", "\n".join(result["errors"]))

    def test_preserves_nonchapter_markdown_heading(self) -> None:
        (self.root / "正文/第001章.md").write_text(chapter(1, "开门", "正文。", heading="# 叙事说明"), encoding="utf-8")
        self.run_export()
        self.assertIn("# 叙事说明", (self.root / "投稿/蛙蛙/book.txt").read_text(encoding="utf-8"))

    def test_rejects_noninteger_number_and_protected_output(self) -> None:
        content = chapter(1, "开门", "正文。").replace("number: 1", "number: true")
        (self.root / "正文/第001章.md").write_text(content, encoding="utf-8")
        result = self.run_export(expect=1)
        self.assertFalse(result["ok"])
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(self.root), "--output", "作品.md", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.root / "作品.md").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "platform has no symlink support")
    def test_rejects_chapter_symlink_outside_project(self) -> None:
        outside = Path(self.temp.name).parent / f"outside-{Path(self.temp.name).name}.md"
        outside.write_text(chapter(1, "外部", "不得导出。"), encoding="utf-8")
        try:
            os.symlink(outside, self.root / "正文/第001章.md")
        except OSError:
            self.skipTest("symlink creation not permitted")
        try:
            result = self.run_export(expect=1)
            self.assertIn("越界", "\n".join(result["errors"]))
        finally:
            outside.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
