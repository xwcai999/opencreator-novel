from __future__ import annotations

import base64
import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "novel-studio-skill" / "skills" / "wawa-submission" / "scripts" / "validate_submission.py"
SPEC = importlib.util.spec_from_file_location("wawa_validate_submission", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class WawaSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cover = self.root / "cover.png"
        self.cover.write_bytes(PNG_1X1)
        self.txt = self.root / "book.txt"
        self.txt.write_text("字" * 20_000, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def metadata(self, **updates: object) -> dict[str, object]:
        value: dict[str, object] = {
            "title": "测试作品",
            "pen_name": "测试作者",
            "summary": "用于离线预检的正式简介。",
            "channel": "男频",
            "status": "连载",
            "categories": ["男频", "游戏竞技", "虚拟网游"],
            "tags": ["爽文"],
            "cover": "cover.png",
        }
        value.update(updates)
        return value

    def validate(self, metadata: dict[str, object] | None = None, **kwargs: object) -> dict[str, object]:
        return MODULE.validate_submission(
            metadata or self.metadata(),
            base_dir=self.root,
            **kwargs,
        )

    def snapshot(self, **updates: object) -> dict[str, object]:
        value: dict[str, object] = {
            "schema_version": "wawa.stats.v1",
            "captured_at": "2026-08-18T12:00:00+08:00",
            "ttl_days": 7,
            "source": {"kind": "synthetic-fixture", "label": "合成测试"},
            "works": [
                {
                    "work_id": "remote-work-001",
                    "title": "不应被投稿预检读取的作品名",
                    "metrics": {"chapters": 3, "words": 1000, "followers": 20, "total_revenue": 1.5},
                    "series": [{"date": "2026-08-18", "followers": 20, "revenue": 1.5}],
                }
            ],
        }
        value.update(updates)
        return value

    def test_optional_fresh_snapshot_is_consumed_without_overwriting_submission(self) -> None:
        result = self.validate(manuscript="book.txt", snapshot=self.snapshot(), snapshot_now="2026-08-18T13:00:00+08:00")
        self.assertTrue(result["ok"], result)
        info = result["wawa_snapshot"]
        self.assertEqual(info["status"], "fresh")
        self.assertEqual(info["aggregate"]["work_count"], 1)
        self.assertEqual(info["aggregate"]["totals"]["words"], 1000)
        self.assertNotIn("remote-work-001", json.dumps(info, ensure_ascii=False))
        self.assertEqual(result["metadata"]["title"], "测试作品")

    def test_stale_snapshot_is_reported_but_not_consumed(self) -> None:
        stale = self.snapshot(captured_at="2026-08-01T12:00:00+08:00")
        works = stale["works"]
        assert isinstance(works, list)
        for work in works:
            assert isinstance(work, dict)
            work["series"] = []
        result = self.validate(
            manuscript="book.txt",
            snapshot=stale,
            snapshot_now="2026-08-18T13:00:00+08:00",
        )
        self.assertTrue(result["ok"], result)
        info = result["wawa_snapshot"]
        self.assertEqual(info["status"], "stale")
        self.assertNotIn("aggregate", info)
        self.assertIn("未实时复核", "\n".join(result["warnings"]))

    def test_invalid_snapshot_does_not_make_material_check_use_partial_data(self) -> None:
        invalid = self.snapshot()
        invalid.pop("schema_version")
        result = self.validate(manuscript="book.txt", snapshot=invalid)
        self.assertTrue(result["ok"], result)
        info = result["wawa_snapshot"]
        self.assertEqual(info["status"], "invalid")
        self.assertNotIn("aggregate", info)
        self.assertTrue(info["errors"])

    def test_independent_txt_mode_passes_without_novel_project(self) -> None:
        result = self.validate(manuscript="book.txt")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["mode"], "independent")
        self.assertEqual(result["word_count_source"], "manuscript")
        self.assertEqual(result["manuscript"]["path"], "book.txt")
        self.assertNotIn(str(self.root), json.dumps(result, ensure_ascii=False))
        self.assertEqual(result["rules"]["public_signing_guidance"]["checked_at"], "2026-08-12")
        self.assertIn("source", result["rules"]["field_and_file_snapshot"])
        self.assertIn("confidence", result["rules"]["historical_form_observation"])
        self.assertIn("stale_after", result["rules"]["public_signing_guidance"])
        self.assertEqual(result["page_verification"]["page_status"], "未实时复核")

    def test_integrated_project_mode_counts_project_body(self) -> None:
        project = self.root / "project"
        (project / "正文").mkdir(parents=True)
        (project / "作品.md").write_text("# 作品", encoding="utf-8")
        (project / "正文" / "001.md").write_text("正文" * 10_000, encoding="utf-8")
        result = self.validate(project_root=project)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["mode"], "integrated")
        self.assertEqual(result["word_count_source"], "project")

    def test_empty_project_cannot_use_declared_word_count(self) -> None:
        project = self.root / "empty-project"
        project.mkdir()
        result = self.validate(self.metadata(word_count=200_000), project_root=project)
        self.assertFalse(result["ok"])
        self.assertIn("不能仅凭元数据声明字数", "\n".join(result["blockers"]))

    def test_fake_image_is_rejected(self) -> None:
        fake = self.root / "fake.jpg"
        fake.write_text("not an image", encoding="utf-8")
        result = self.validate(self.metadata(cover="fake.jpg"), manuscript="book.txt")
        self.assertFalse(result["ok"])
        self.assertIn("JPEG 文件结构无效", "\n".join(result["errors"]))

    def test_fake_docx_is_rejected(self) -> None:
        fake = self.root / "fake.docx"
        fake.write_text("not a zip", encoding="utf-8")
        result = self.validate(manuscript="fake.docx")
        self.assertFalse(result["ok"])
        self.assertIn("DOCX 解析失败", "\n".join(result["errors"]))

    def test_real_minimal_docx_is_parsed(self) -> None:
        docx = self.root / "book.docx"
        content_types = '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
        document = (
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>' + ("字" * 20_000) + '</w:t></w:r></w:p></w:body></w:document>'
        )
        with zipfile.ZipFile(docx, "w") as archive:
            archive.writestr("[Content_Types].xml", content_types)
            archive.writestr("word/document.xml", document)
        result = self.validate(manuscript="book.docx")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["word_count"], 20_000)

    def test_parent_path_escape_is_rejected(self) -> None:
        outside = self.root.parent / (self.root.name + "-outside.txt")
        try:
            outside.write_text("字" * 20_000, encoding="utf-8")
            result = self.validate(manuscript=f"../{outside.name}")
            self.assertFalse(result["ok"])
            self.assertIn("路径越界", "\n".join(result["errors"]))
        finally:
            outside.unlink(missing_ok=True)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unsupported")
    def test_symlink_escape_is_rejected_when_available(self) -> None:
        outside = self.root.parent / (self.root.name + "-outside.txt")
        link = self.root / "linked.txt"
        try:
            outside.write_text("字" * 20_000, encoding="utf-8")
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlink creation unavailable")
            result = self.validate(manuscript="linked.txt")
            self.assertFalse(result["ok"])
            self.assertIn("路径越界", "\n".join(result["errors"]))
        finally:
            link.unlink(missing_ok=True)
            outside.unlink(missing_ok=True)

    def test_historical_thresholds_are_warnings_not_claimed_signing_rules(self) -> None:
        short = self.root / "short.txt"
        short.write_text("字" * 10_000, encoding="utf-8")
        result = self.validate(manuscript="short.txt")
        self.assertTrue(result["ok"], result)
        warnings = "\n".join(result["warnings"])
        self.assertIn("10 万字", warnings)
        self.assertIn("历史页面快照", warnings)
        expected_status = result["rules"]["historical_form_observation"]["verification_status"]
        self.assertIn(expected_status, warnings)
        self.assertNotIn("签约口径为 2 万字", json.dumps(result, ensure_ascii=False))

    def test_bundled_taxonomy_accepts_exact_path_and_tag(self) -> None:
        result = self.validate(manuscript="book.txt")
        self.assertTrue(result["ok"], result)
        taxonomy = result["taxonomy"]
        self.assertEqual(taxonomy["category_snapshot"]["path_count"], 350)
        self.assertEqual(taxonomy["tag_snapshot"]["tag_count"], 158)
        self.assertTrue(taxonomy["categories"]["valid"])
        self.assertTrue(taxonomy["categories"]["channel_root_valid"])
        self.assertTrue(taxonomy["tags"]["valid"])
        self.assertNotIn("path", taxonomy["tag_snapshot"]["source"])

    def test_taxonomy_rejects_unknown_category_and_tag(self) -> None:
        result = self.validate(
            self.metadata(categories=["男频", "游戏竞技", "不存在的分类"], tags=["不存在的标签"]),
            manuscript="book.txt",
        )
        self.assertFalse(result["ok"])
        errors = "\n".join(result["errors"])
        self.assertIn("三级类目不在固定作品分类快照中", errors)
        self.assertIn("作品标签不在固定标签库中", errors)

    def test_taxonomy_rejects_channel_root_mismatch(self) -> None:
        result = self.validate(
            self.metadata(channel="女频", categories=["男频", "游戏竞技", "虚拟网游"]),
            manuscript="book.txt",
        )
        self.assertFalse(result["ok"])
        self.assertIn("女频频道只能选择以“女频”为根", "\n".join(result["errors"]))

    def test_custom_snapshot_requires_fixed_contract_metadata(self) -> None:
        category_snapshot = self.root / "category-snapshot.json"
        category_snapshot.write_text(
            json.dumps({"categories": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        result = self.validate(manuscript="book.txt", category_snapshot="category-snapshot.json")
        self.assertFalse(result["ok"])
        self.assertIn("固定快照元数据不匹配", "\n".join(result["errors"]))

    def test_taxonomy_output_identifies_strict_migration_contract(self) -> None:
        result = self.validate(manuscript="book.txt")
        self.assertEqual(result["taxonomy"]["policy"], "strict-v1")
        self.assertEqual(
            result["taxonomy"]["category_snapshot"]["source"]["url"],
            "https://wawawriter.com/app/submission/create",
        )


if __name__ == "__main__":
    unittest.main()
