from __future__ import annotations

import argparse
import base64
import json
import tempfile
import unittest
from pathlib import Path

from run_page_workflow import build_command, preflight_execution_package, resolve_engine


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class PageWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.engine = self.root / "wawa-submission-playwright.mjs"
        self.engine.write_text("", encoding="utf-8")
        self.metadata = self.root / "package.json"
        self.metadata.write_text("{}", encoding="utf-8")
        self.cover = self.root / "cover.png"
        self.cover.write_bytes(PNG_1X1)
        self.manuscript = self.root / "manuscript.txt"
        self.manuscript.write_text("正文", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def args(self, action: str, **overrides: object) -> argparse.Namespace:
        values = {
            "action": action,
            "node": "node",
            "metadata": "",
            "campaign_code": "",
            "run_id": "",
            "config": "",
            "snapshot": "",
            "allow_live": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_resolve_engine_requires_expected_entry_name(self) -> None:
        self.assertEqual(resolve_engine(str(self.engine)), self.engine.resolve())
        other = self.root / "unsafe.mjs"
        other.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "入口文件名"):
            resolve_engine(str(other))

    def test_prepare_builds_prefill_command_only(self) -> None:
        command = build_command(
            self.args(
                "prepare",
                metadata=str(self.metadata),
                campaign_code="verified-code",
                allow_live=True,
            ),
            self.engine,
        )
        self.assertIn("--prepare", command)
        self.assertIn("--campaign-code", command)
        self.assertNotIn("--submit", command)

    def test_live_actions_require_explicit_allow_live(self) -> None:
        for action in ("prepare", "login", "campaigns"):
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, "--allow-live"):
                build_command(
                    self.args(action, metadata=str(self.metadata) if action == "prepare" else ""),
                    self.engine,
                )

    def test_page_preflight_requires_v2_and_real_file_content(self) -> None:
        legacy = self.root / "legacy.json"
        legacy.write_text(json.dumps({"title": "旧材料"}, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "只消费 schema v2"):
            preflight_execution_package(legacy)

        package = {
            "schema_version": 2,
            "type": "wawa-submission-package",
            "title": "页面预检作品",
            "pen_name": "作者",
            "summary": "正式简介",
            "channel": "全频",
            "status": "完结",
            "category": "短篇",
            "categories": ["出版", "短篇", "现代都市"],
            "tags": ["现代"],
            "custom_tags": [],
            "cover": str(self.cover),
            "manuscript": str(self.manuscript),
            "campaign": {"name": "目标活动", "match_mode": "exact", "code": ""},
            "workflow": {"mode": "page_prefill", "final_submit": "human_only"},
        }
        self.metadata.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(preflight_execution_package(self.metadata)["ok"])

        self.cover.write_bytes(b"not-a-real-png")
        with self.assertRaisesRegex(ValueError, "PNG 文件结构无效"):
            preflight_execution_package(self.metadata)


if __name__ == "__main__":
    unittest.main()
