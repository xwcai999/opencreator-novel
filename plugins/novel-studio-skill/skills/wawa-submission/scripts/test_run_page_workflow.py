from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from run_page_workflow import build_command, resolve_engine


class PageWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.engine = self.root / "wawa-submission-playwright.mjs"
        self.engine.write_text("", encoding="utf-8")
        self.metadata = self.root / "package.json"
        self.metadata.write_text("{}", encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()

