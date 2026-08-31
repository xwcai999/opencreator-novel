from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from validate_submission import (
    COVER_MAX_BYTES,
    MANUSCRIPT_MAX_BYTES,
    validate_project_adapter,
    validate_submission,
)


class ValidateSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.cover = self.root / "cover.jpg"
        self.cover.write_bytes(b"cover")
        self.manuscript = self.root / "manuscript.txt"
        self.manuscript.write_text("字" * 20_000, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def metadata(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": 2,
            "type": "wawa-submission-package",
            "title": "一部合规作品",
            "pen_name": "作者",
            "summary": "简介",
            "channel": "男频",
            "status": "连载",
            "categories": ["男频", "玄幻奇幻", "东方玄幻"],
            "tags": ["热血"],
            "custom_tags": ["热血"],
            "cover": str(self.cover),
            "word_count": 20_000,
            "campaign": {
                "name": "第一届「退款与退场」微观情感叙事大赛",
                "match_mode": "exact",
                "code": "",
            },
            "workflow": {"mode": "page_prefill", "final_submit": "human_only"},
        }
        value.update(overrides)
        return value

    def test_valid_metadata_and_txt_manuscript(self) -> None:
        result = validate_submission(self.metadata(), manuscript=self.manuscript)
        self.assertTrue(result["ok"])
        self.assertEqual(result["word_count"], 20_000)
        self.assertEqual(result["word_count_source"], "manuscript")
        self.assertFalse(result["errors"])
        self.assertTrue(result["taxonomy"]["categories"]["valid"])
        self.assertTrue(result["taxonomy"]["tags"]["valid"])
        self.assertEqual(result["taxonomy"]["category_snapshot"]["path_count"], 350)
        self.assertEqual(result["taxonomy"]["tag_snapshot"]["tag_count"], 158)

    def test_category_requires_exact_path_and_channel_root(self) -> None:
        invalid = validate_submission(
            self.metadata(categories=["男频", "玄幻奇幻", "不存在分类"]),
            manuscript=self.manuscript,
        )
        self.assertFalse(invalid["ok"])
        self.assertIn("不在固定作品分类快照", "\n".join(invalid["errors"]))
        self.assertFalse(invalid["taxonomy"]["categories"]["valid"])

        cross_channel = validate_submission(
            self.metadata(categories=["女频", "浪漫青春", "青春校园"]),
            manuscript=self.manuscript,
        )
        self.assertFalse(cross_channel["ok"])
        self.assertIn("男频频道只能选择", "\n".join(cross_channel["errors"]))
        self.assertTrue(cross_channel["taxonomy"]["categories"]["valid"])
        self.assertFalse(cross_channel["taxonomy"]["categories"]["channel_root_valid"])

        all_channel = validate_submission(
            self.metadata(channel="全频", categories=["女频", "浪漫青春", "青春校园"]),
            manuscript=self.manuscript,
        )
        self.assertTrue(all_channel["ok"])
        self.assertTrue(all_channel["taxonomy"]["categories"]["channel_root_valid"])

    def test_tags_must_come_from_fixed_snapshot(self) -> None:
        result = validate_submission(
            self.metadata(tags=["热血", "不存在标签"]),
            manuscript=self.manuscript,
        )
        self.assertFalse(result["ok"])
        self.assertIn("不存在标签", "\n".join(result["errors"]))
        self.assertEqual(result["taxonomy"]["tags"]["unknown"], ["不存在标签"])

    def test_missing_and_corrupt_taxonomy_snapshots_are_errors(self) -> None:
        missing = validate_submission(
            self.metadata(),
            manuscript=self.manuscript,
            category_snapshot=self.root / "missing-categories.json",
        )
        self.assertFalse(missing["ok"])
        self.assertIn("无法读取作品分类快照", "\n".join(missing["errors"]))
        self.assertFalse(missing["taxonomy"]["category_snapshot"]["loaded"])

        corrupt = self.root / "bad-tags.json"
        corrupt.write_text("{not-json", encoding="utf-8")
        damaged = validate_submission(
            self.metadata(),
            manuscript=self.manuscript,
            tag_snapshot=corrupt,
        )
        self.assertFalse(damaged["ok"])
        self.assertIn("无法读取作品标签快照", "\n".join(damaged["errors"]))
        self.assertFalse(damaged["taxonomy"]["tag_snapshot"]["loaded"])

    def test_taxonomy_snapshot_integrity_checks_counts_and_duplicates(self) -> None:
        category_snapshot = self.root / "bad-categories.json"
        category_snapshot.write_text(
            json.dumps(
                {
                    "path_count": 2,
                    "categories": [
                        {
                            "label": "男频",
                            "children": [
                                {"label": "大类", "children": [{"label": "小类"}]}
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        category_result = validate_submission(
            self.metadata(), manuscript=self.manuscript, category_snapshot=category_snapshot
        )
        self.assertIn("path_count 与实际三级路径数量不一致", "\n".join(category_result["errors"]))

        duplicate_category_snapshot = self.root / "duplicate-categories.json"
        duplicate_category_snapshot.write_text(
            json.dumps(
                {
                    "categories": [
                        {
                            "label": "男频",
                            "children": [
                                {
                                    "label": "大类",
                                    "children": [{"label": "小类"}, {"label": "小类"}],
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        duplicate_category_result = validate_submission(
            self.metadata(), manuscript=self.manuscript, category_snapshot=duplicate_category_snapshot
        )
        self.assertIn("存在重复完整三级路径", "\n".join(duplicate_category_result["errors"]))

        tag_snapshot = self.root / "bad-tags-count.json"
        tag_snapshot.write_text(
            json.dumps({"count": 2, "tags": ["固定标签"]}, ensure_ascii=False), encoding="utf-8"
        )
        tag_result = validate_submission(
            self.metadata(), manuscript=self.manuscript, tag_snapshot=tag_snapshot
        )
        self.assertIn("count 与实际标签数量不一致", "\n".join(tag_result["errors"]))

        duplicate_tag_snapshot = self.root / "duplicate-tags.json"
        duplicate_tag_snapshot.write_text(
            json.dumps({"tags": ["固定标签", "固定标签"]}, ensure_ascii=False), encoding="utf-8"
        )
        duplicate_tag_result = validate_submission(
            self.metadata(), manuscript=self.manuscript, tag_snapshot=duplicate_tag_snapshot
        )
        self.assertIn("存在重复标签", "\n".join(duplicate_tag_result["errors"]))

    def test_field_limits_and_required_values(self) -> None:
        result = validate_submission(
            self.metadata(
                title="长" * 201,
                pen_name="",
                summary="简" * 501,
                channel="未知",
                status="未知",
                categories=["只有", "两项"],
                tags=[],
                custom_tags=["超长自定义标签123456"],
            )
        )
        self.assertFalse(result["ok"])
        joined = "\n".join([*result["errors"], *result["blockers"]])
        for phrase in ("作品名称", "笔名", "简介", "频道", "状态", "三级类目", "标签", "自定义标签"):
            self.assertIn(phrase, joined)

    def test_word_count_is_informational_and_never_blocks_prefill(self) -> None:
        serial = validate_submission(self.metadata(word_count=19_999), manuscript=None, project_root=self.root)
        self.assertTrue(serial["ok"])
        self.assertFalse(serial["blockers"])
        self.assertIn("不阻断预填", "\n".join(serial["warnings"]))

        completed = validate_submission(
            self.metadata(status="完结", word_count=25_000),
            manuscript=None,
            project_root=self.root,
        )
        self.assertTrue(completed["ok"])
        self.assertFalse(completed["blockers"])
        self.assertIn("不阻断预填", "\n".join(completed["warnings"]))

    def test_execution_contract_rejects_unsafe_workflow(self) -> None:
        result = validate_submission(
            self.metadata(workflow={"mode": "page_prefill", "final_submit": "automatic"}),
            manuscript=self.manuscript,
        )
        self.assertFalse(result["ok"])
        self.assertIn("human_only", "\n".join(result["errors"]))

        invalid_campaign = validate_submission(
            self.metadata(campaign={"name": "目标活动", "match_mode": "first", "code": ""}),
            manuscript=self.manuscript,
        )
        self.assertFalse(invalid_campaign["ok"])
        self.assertIn("match_mode 必须为 exact", "\n".join(invalid_campaign["errors"]))

    def test_legacy_flat_metadata_remains_compatible(self) -> None:
        legacy = self.metadata()
        for key in ("schema_version", "type", "campaign", "workflow"):
            legacy.pop(key)
        result = validate_submission(legacy, manuscript=self.manuscript)
        self.assertTrue(result["ok"])

    def test_required_cover_manuscript_and_summary(self) -> None:
        result = validate_submission(
            self.metadata(cover="", summary=""),
        )
        self.assertFalse(result["ok"])
        joined = "\n".join(result["blockers"])
        self.assertIn("作品封面", joined)
        self.assertIn("正文来源", joined)
        self.assertIn("作品简介", joined)

    def test_history_achievement_images(self) -> None:
        history = self.root / "history.png"
        history.write_bytes(b"proof")
        result = validate_submission(
            self.metadata(history_achievement_images=[str(history)]),
            manuscript=self.manuscript,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["history_achievement_images"]), 1)

        too_many = validate_submission(
            self.metadata(history_achievement_images=[str(history)] * 11),
            manuscript=self.manuscript,
        )
        self.assertFalse(too_many["ok"])
        self.assertIn("1—10", "\n".join(too_many["errors"]))

        missing_with_declared_size = validate_submission(
            self.metadata(
                history_achievement_images=[
                    {"path": str(self.root / "missing.png"), "size_bytes": 1}
                ]
            ),
            manuscript=self.manuscript,
        )
        self.assertFalse(missing_with_declared_size["ok"])
        self.assertIn("文件不存在", "\n".join(missing_with_declared_size["errors"]))

    def test_declared_size_cannot_replace_local_files(self) -> None:
        result = validate_submission(
            self.metadata(
                cover={"path": str(self.root / "missing.jpg"), "size_bytes": 1},
            ),
            manuscript={"path": str(self.root / "missing.txt"), "size_bytes": 1},
        )
        self.assertFalse(result["ok"])
        joined = "\n".join(result["errors"])
        self.assertIn("封面文件不存在", joined)
        self.assertIn("投稿文件文件不存在", joined)

    def test_cover_and_manuscript_limits(self) -> None:
        large_cover = self.root / "large.png"
        large_cover.write_bytes(b"0" * (COVER_MAX_BYTES + 1))
        invalid_manuscript = self.root / "draft.pdf"
        invalid_manuscript.write_bytes(b"draft")
        result = validate_submission(self.metadata(cover=str(large_cover)), manuscript=invalid_manuscript)
        self.assertFalse(result["ok"])
        joined = "\n".join(result["errors"])
        self.assertIn("封面文件过大", joined)
        self.assertIn("投稿文件扩展名不支持", joined)

    def test_project_adapter_reads_only_submission_materials(self) -> None:
        (self.root / "作品.md").write_text("# 作品\n", encoding="utf-8")
        body = self.root / "正文"
        body.mkdir()
        (body / "第一章.md").write_text("正文" * 100, encoding="utf-8")
        (self.root / "设定").mkdir()
        (self.root / "设定" / "private.txt").write_text("不应读取", encoding="utf-8")
        reports = self.root / "报告" / "章节审查"
        reports.mkdir(parents=True)
        (reports / "review.md").write_text("报告", encoding="utf-8")
        result = validate_project_adapter(self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["word_count"], 200)
        self.assertIn("作品.md", result["read_files"])
        self.assertIn("正文/第一章.md", result["read_files"])
        self.assertNotIn("设定/private.txt", result["read_files"])
        self.assertIn("报告/章节审查/review.md", result["report_files"])

    def test_cli_json_output(self) -> None:
        metadata_path = self.root / "metadata.json"
        metadata_path.write_text(json.dumps(self.metadata(), ensure_ascii=False), encoding="utf-8")
        script = Path(__file__).with_name("validate_submission.py")
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--metadata",
                str(metadata_path),
                "--manuscript",
                str(self.manuscript),
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])

    def test_cli_snapshot_overrides(self) -> None:
        category_snapshot = self.root / "categories.json"
        category_snapshot.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "categories": [
                        {
                            "label": "男频",
                            "children": [
                                {
                                    "label": "自定义大类",
                                    "children": [{"label": "自定义小类"}],
                                }
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        tag_snapshot = self.root / "tags.json"
        tag_snapshot.write_text(
            json.dumps({"schema_version": 1, "tags": ["固定标签"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        metadata_path = self.root / "metadata-override.json"
        metadata_path.write_text(
            json.dumps(
                self.metadata(
                    categories=["男频", "自定义大类", "自定义小类"],
                    tags=["固定标签"],
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        script = Path(__file__).with_name("validate_submission.py")
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--metadata",
                str(metadata_path),
                "--manuscript",
                str(self.manuscript),
                "--category-snapshot",
                str(category_snapshot),
                "--tag-snapshot",
                str(tag_snapshot),
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["taxonomy"]["tag_snapshot"]["path"], str(tag_snapshot.resolve()))


if __name__ == "__main__":
    unittest.main()


