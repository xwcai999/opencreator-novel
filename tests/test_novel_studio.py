from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "novel-studio-skill" / "skills" / "novel-studio" / "scripts"
PYTHON = sys.executable


def run_script(name: str, *args: object, expect: int = 0) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    command = [PYTHON, str(SCRIPT_ROOT / name), *(str(arg) for arg in args)]
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        env=environment,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"命令返回码 {result.returncode}，预期 {expect}: {' '.join(command)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    payload = json.loads(result.stdout)
    return result, payload


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


class NovelStudioTests(unittest.TestCase):
    def init_project(self, root: Path, scope: str, complexity: str, driver: str) -> None:
        _, payload = run_script(
            "init_project.py",
            "--project-root",
            root,
            "--title",
            f"{scope}-测试书",
            "--scope",
            scope,
            "--complexity",
            complexity,
            "--primary-driver",
            driver,
        )
        self.assertTrue(payload["ok"])

    def add_continuity_fixture(self, root: Path) -> None:
        write(
            root / "设定/角色/林澈.md",
            """---
type: character
id: character-lin-che
name: 林澈
status: active
relationships: []
---

# 林澈

她负责维护旧钟楼。
""",
        )
        write(
            root / "设定/世界观/钟楼.md",
            """---
type: location
id: location-clocktower
name: 旧钟楼
---

# 旧钟楼

每逢潮汐都会改变内部道路。
""",
        )
        write(
            root / "大纲/卷纲/第一幕.md",
            """---
type: arc
id: arc-first
name: 第一幕
status: active
---

# 第一幕

林澈决定修复钟楼。
""",
        )
        write(
            root / "大纲/细纲/第2章.md",
            """---
type: chapter-outline
id: chapter-outline-002
number: 2
title: 逆潮
expectations-advanced: []
expectations-fulfilled: []
expectations-forbidden: []
continuity-sources: [设定/角色/林澈.md, 设定/世界观/钟楼.md]
---

# 第二章细纲

林澈在旧钟楼追踪逆向潮声。
""",
        )
        write(
            root / "正文/第1章_钟声.md",
            """---
type: chapter
id: chapter-001
number: 1
title: 钟声
status: accepted
pov: character-lin-che
characters: [character-lin-che]
mentions: []
locations: [location-clocktower]
arcs-advanced: [arc-first]
allow-deceased-present: []
---

# 第一章 钟声

林澈登上旧钟楼，第一次听见逆着潮水响起的钟声。
""",
        )
        state_path = root / "状态/当前状态.md"
        state_text = state_path.read_text(encoding="utf-8").replace(
            "last-accepted-chapter: 0", "last-accepted-chapter: 1"
        )
        write(state_path, state_text)
        run_script(
            "record_chapter_review.py",
            "--project-root",
            root,
            "--chapter",
            1,
            "--rounds",
            1,
            "--author-passed",
            "--reader-passed",
            "--style-passed",
            "--rereview-passed",
        )

    def test_short_medium_long_profiles_and_unbiased_driver(self) -> None:
        cases = (
            ("short", "light", "experiential"),
            ("medium", "standard", "relationship"),
            ("long", "extended", "information"),
        )
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for scope, complexity, driver in cases:
                root = base / scope
                self.init_project(root, scope, complexity, driver)
                _, validation = run_script("validate_project.py", "--project-root", root)
                self.assertTrue(validation["ok"], validation)
                project_text = (root / "作品.md").read_text(encoding="utf-8")
                self.assertIn(f"scope: {scope}", project_text)
                self.assertIn(f"complexity: {complexity}", project_text)
                self.assertIn(f"primary-driver: {driver}", project_text)
            short_positioning = (base / "short/设定/题材定位.md").read_text(encoding="utf-8")
            self.assertIn("长期叙事驱动力", short_positioning)
            self.assertNotIn("长线悬念", short_positioning)
            self.assertNotIn("最终真相", short_positioning)

    def test_style_profile_is_optional_inactive_by_default_and_loaded_only_when_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "book"
            self.init_project(root, "medium", "standard", "relationship")
            profile = root / "设定/文风档案.md"
            self.assertTrue(profile.is_file())
            profile_text = profile.read_text(encoding="utf-8")
            self.assertIn("type: style-profile", profile_text)
            self.assertIn("status: inactive", profile_text)

            inactive_context_path = root / "索引/context-pack-inactive.md"
            _, inactive_context = run_script(
                "build_context_pack.py",
                "--project-root",
                root,
                "--query",
                "文风 AI腔",
                "--output",
                inactive_context_path,
            )
            self.assertNotIn("设定/文风档案.md", inactive_context["included"])
            _, inactive_retrieval = run_script(
                "retrieve_context.py",
                "--project-root",
                root,
                "--query",
                "文风 AI腔",
            )
            self.assertNotIn("设定/文风档案.md", [item["path"] for item in inactive_retrieval["results"]])

            profile_text = profile_text.replace("status: inactive", "status: active").replace(
                "- 明确避免：待确认", "- 明确避免：结论先行的解释腔"
            )
            write(profile, profile_text)
            active_context_path = root / "索引/context-pack-active.md"
            _, active_context = run_script(
                "build_context_pack.py",
                "--project-root",
                root,
                "--query",
                "下一章关系变化",
                "--output",
                active_context_path,
            )
            self.assertIn("设定/文风档案.md", active_context["included"])

            profile.unlink()
            _, old_project_validation = run_script("validate_project.py", "--project-root", root)
            self.assertTrue(old_project_validation["ok"], old_project_validation)
            no_profile_context_path = root / "索引/context-pack-no-profile.md"
            _, no_profile_context = run_script(
                "build_context_pack.py",
                "--project-root",
                root,
                "--query",
                "下一章关系变化",
                "--output",
                no_profile_context_path,
            )
            self.assertNotIn("设定/文风档案.md", no_profile_context["included"])

            model_policy = (SCRIPT_ROOT.parent / "references/model-policy.md").read_text(encoding="utf-8")
            for concrete_model in ("gpt-5", "claude-", "gemini-", "deepseek-"):
                self.assertNotIn(concrete_model, model_policy.lower())

    def test_validation_retrieval_context_and_index_idempotence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            self.init_project(root, "long", "extended", "quest")
            self.add_continuity_fixture(root)

            _, validation = run_script("validate_project.py", "--project-root", root)
            self.assertTrue(validation["ok"], validation)
            self.assertEqual(validation["counts"]["chapters"], 1)

            _, retrieval = run_script(
                "retrieve_context.py",
                "--project-root",
                root,
                "--query",
                "林澈 旧钟楼 逆潮",
            )
            paths = [item["path"] for item in retrieval["results"]]
            self.assertIn("设定/角色/林澈.md", paths)
            self.assertTrue(any("钟楼" in path for path in paths))

            context_path = root / "索引/context-pack-2.md"
            _, context = run_script(
                "build_context_pack.py",
                "--project-root",
                root,
                "--chapter",
                2,
                "--query",
                "林澈在旧钟楼追踪逆潮",
                "--output",
                context_path,
            )
            self.assertIn("正文/第1章_钟声.md", context["included"])
            self.assertIn("大纲/细纲/第2章.md", context["included"])
            self.assertIn("设定/读者契约.md", context["included"])
            self.assertIn("字符预算：36000", context_path.read_text(encoding="utf-8"))

            index_path = root / "索引/project-index.json"
            run_script("reindex_project.py", "--project-root", root)
            first = index_path.read_bytes()
            run_script("reindex_project.py", "--project-root", root)
            self.assertEqual(first, index_path.read_bytes())

    def test_hard_gate_rejects_missing_reference_and_dead_character(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            self.init_project(root, "medium", "standard", "growth")
            self.add_continuity_fixture(root)
            broken = (root / "正文/第1章_钟声.md").read_text(encoding="utf-8").replace(
                "characters: [character-lin-che]", "characters: [character-missing]"
            )
            write(root / "正文/第1章_钟声.md", broken)
            _, missing = run_script("validate_project.py", "--project-root", root, expect=1)
            self.assertTrue(any("引用不存在的角色 character-missing" in item for item in missing["errors"]))

            write(root / "正文/第1章_钟声.md", broken.replace("character-missing", "character-lin-che"))
            character_path = root / "设定/角色/林澈.md"
            dead = character_path.read_text(encoding="utf-8").replace(
                "status: active", "status: dead\ndied-in: 1"
            )
            write(character_path, dead)
            write(
                root / "正文/第2章_回返.md",
                """---
type: chapter
id: chapter-002
number: 2
title: 回返
status: draft
pov: character-lin-che
characters: [character-lin-che]
mentions: []
locations: [location-clocktower]
arcs-advanced: [arc-first]
allow-deceased-present: []
---

# 第二章 回返

林澈走入钟楼。
""",
            )
            _, dead_result = run_script("validate_project.py", "--project-root", root, expect=1)
            self.assertTrue(any("已死亡角色 character-lin-che" in item for item in dead_result["errors"]))

    def test_migration_is_copy_only_and_normalizes_legacy_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "legacy"
            target = base / "migrated"
            write(source / "设定/角色/林澈.md", "# 林澈\n\n旧钟楼维护者。\n")
            write(source / "设定/杂记.md", "# 杂记\n\n此文件没有 frontmatter。\n")
            write(source / "大纲/大纲.md", "# 大纲\n\n修复钟楼。\n")
            write(source / "大纲/细纲_第1章.md", "# 第一章细纲\n\n听见钟声。\n")
            write(source / "正文/第1章_钟声.md", "# 第一章\n\n她听见钟声。\n")
            write(source / "追踪/上下文.md", "# 上下文\n\n第一章已完成。\n")
            write(source / "封面/旧封面-某某著.png", "legacy cover placeholder")
            before = tree_digest(source)

            _, migrated = run_script(
                "migrate_project.py",
                "--source",
                source,
                "--target",
                target,
                "--title",
                "钟楼",
                "--scope",
                "medium",
                "--complexity",
                "standard",
                "--primary-driver",
                "growth",
            )
            self.assertTrue(migrated["ok"])
            self.assertFalse(migrated["source_modified"])
            self.assertEqual(before, tree_digest(source))
            self.assertTrue((target / "报告/迁移报告.md").is_file())
            self.assertFalse((target / "封面/旧封面-某某著.png").exists())
            migration_report = (target / "报告/迁移报告.md").read_text(encoding="utf-8")
            self.assertIn("旧封面-某某著.png", migration_report)
            self.assertIn("必须按无笔名封面工作流重新生成", migration_report)
            self.assertTrue((target / "设定/杂记.md").read_text(encoding="utf-8").startswith("---\n"))
            migrated_profile = (target / "设定/文风档案.md").read_text(encoding="utf-8")
            self.assertIn("status: inactive", migrated_profile)
            _, validation = run_script("validate_project.py", "--project-root", target)
            self.assertTrue(validation["ok"], validation)

    def test_cover_title_only_policy_accepts_title_and_rejects_extra_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            _, initialized = run_script(
                "init_project.py",
                "--project-root",
                root,
                "--title",
                "潮汐钟楼",
                "--scope",
                "short",
                "--complexity",
                "light",
                "--primary-driver",
                "experiential",
            )
            self.assertTrue(initialized["ok"])
            cover = root / "封面/cover-native.png"
            prompt = root / "封面/cover-prompt.md"
            Image.new("RGB", (1200, 1800), (35, 51, 72)).save(cover)
            write(
                prompt,
                "直接生成完整封面，画面与书名一次生成；可见文字逐字为潮汐钟楼，只允许该书名，"
                "无作者名、无笔名、无署名、无签名、无 Logo、无水印。",
            )
            _, recorded = run_script(
                "record_generated_cover.py",
                "--project-root",
                root,
                "--image",
                cover,
                "--prompt-file",
                prompt,
            )
            self.assertTrue(recorded["ok"])
            self.assertEqual(recorded["generation_mode"], "model-native-title")
            self.assertFalse(recorded["post_generated_text_edit"])
            self.assertEqual(recorded["visible_text"], ["潮汐钟楼"])
            self.assertFalse(recorded["author_attribution_present"])

            _, accepted = run_script(
                "validate_cover_text.py",
                "--project-root",
                root,
                "--image",
                cover,
                "--prompt-file",
                prompt,
                "--ocr-text",
                "潮汐钟楼",
                "--manual-review-passed",
                "--output",
                root / "报告/封面/validation.json",
            )
            self.assertTrue(accepted["ok"])

            _, rejected = run_script(
                "validate_cover_text.py",
                "--project-root",
                root,
                "--image",
                cover,
                "--prompt-file",
                prompt,
                "--ocr-text",
                "潮汐钟楼 某某著",
                "--manual-review-passed",
                expect=1,
            )
            self.assertFalse(rejected["ok"])
            self.assertTrue(any("书名以外" in item for item in rejected["errors"]))

            artwork = root / "封面/artwork.png"
            overlay = root / "封面/cover-overlay.png"
            Image.new("RGB", (1200, 1800), (20, 30, 40)).save(artwork)
            _, rendered = run_script(
                "render_cover_title.py",
                "--project-root",
                root,
                "--artwork",
                artwork,
                "--output",
                overlay,
            )
            self.assertEqual(rendered["generation_mode"], "deterministic-overlay")
            _, overlay_rejected = run_script(
                "validate_cover_text.py",
                "--project-root",
                root,
                "--image",
                overlay,
                "--prompt-file",
                prompt,
                "--ocr-text",
                "潮汐钟楼",
                "--manual-review-passed",
                expect=1,
            )
            self.assertTrue(any("拒绝无字底图或后期叠字" in item for item in overlay_rejected["errors"]))

            help_result = subprocess.run(
                [PYTHON, str(SCRIPT_ROOT / "record_generated_cover.py"), "--help"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                check=True,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            for option in ("--author", "--pen-name", "--byline", "--subtitle"):
                self.assertNotIn(option, help_result.stdout)
            self.assertNotIn("--title", help_result.stdout)

    def test_all_optional_outputs_stay_inside_target_project_or_cover_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / "book"
            outside = base / "outside.json"
            self.init_project(project, "short", "light", "experiential")

            for script, args in (
                (
                    "retrieve_context.py",
                    ("--project-root", project, "--query", "雨", "--output", outside),
                ),
                (
                    "validate_project.py",
                    ("--project-root", project, "--output", outside),
                ),
                (
                    "reindex_project.py",
                    ("--project-root", project, "--output", outside),
                ),
            ):
                _, payload = run_script(script, *args, expect=2 if script != "reindex_project.py" else 1)
                self.assertFalse(payload["ok"])
                self.assertIn("路径越界", payload["error"])
                self.assertFalse(outside.exists())

            cover = project / "封面/cover-native.png"
            prompt = project / "封面/cover-prompt.md"
            Image.new("RGB", (600, 900), (20, 30, 40)).save(cover)
            write(
                prompt,
                "直接生成完整封面，画面与书名一次生成；只允许 short-测试书；"
                "无作者名、无笔名、无署名、无签名、无水印。",
            )
            _, record_error = run_script(
                "record_generated_cover.py",
                "--project-root",
                project,
                "--image",
                cover,
                "--prompt-file",
                prompt,
                "--output",
                base / "outside.json",
                expect=1,
            )
            self.assertFalse(record_error["ok"])
            self.assertIn("路径越界", record_error["error"])

    def test_derived_outputs_cannot_overwrite_authoritative_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "book"
            self.init_project(project, "short", "light", "experiential")
            work = project / "作品.md"
            before = work.read_bytes()
            cases = (
                (
                    "retrieve_context.py",
                    ("--project-root", project, "--query", "雨", "--output", work),
                    2,
                ),
                ("validate_project.py", ("--project-root", project, "--output", work), 2),
                ("reindex_project.py", ("--project-root", project, "--output", work), 1),
                (
                    "build_context_pack.py",
                    ("--project-root", project, "--chapter", 1, "--output", work),
                    1,
                ),
            )
            for script, args, code in cases:
                _, payload = run_script(script, *args, expect=code)
                self.assertFalse(payload["ok"])
                self.assertIn("路径越界", payload["error"])
                self.assertEqual(before, work.read_bytes())

    def test_schema_v2_binds_accepted_chapter_to_reviewed_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "book"
            self.init_project(project, "short", "light", "growth")
            self.add_continuity_fixture(project)
            chapter = project / "正文/第1章_钟声.md"
            changed = chapter.read_text(encoding="utf-8").replace("第一次听见", "再次听见")
            write(chapter, changed)
            _, payload = run_script("validate_project.py", "--project-root", project, expect=1)
            self.assertTrue(any("正文哈希已变化" in error for error in payload["errors"]))

    def test_replacing_review_requires_changed_body_and_archives_previous_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "book"
            self.init_project(project, "short", "light", "growth")
            self.add_continuity_fixture(project)
            report = project / "报告/章节审查/chapter-001.json"
            previous = json.loads(report.read_text(encoding="utf-8"))

            _, unchanged = run_script(
                "record_chapter_review.py",
                "--project-root",
                project,
                "--chapter",
                1,
                "--rounds",
                2,
                "--author-passed",
                "--reader-passed",
                "--style-passed",
                "--rereview-passed",
                "--replace-existing",
                expect=1,
            )
            self.assertIn("正文哈希未变化", unchanged["error"])
            self.assertEqual(previous, json.loads(report.read_text(encoding="utf-8")))
            self.assertFalse((report.parent / "历史").exists())

            chapter = project / "正文/第1章_钟声.md"
            write(chapter, chapter.read_text(encoding="utf-8").replace("第一次听见", "再次听见"))
            _, replaced = run_script(
                "record_chapter_review.py",
                "--project-root",
                project,
                "--chapter",
                1,
                "--rounds",
                2,
                "--author-passed",
                "--reader-passed",
                "--style-passed",
                "--rereview-passed",
                "--replace-existing",
            )
            self.assertTrue(replaced["replaces_existing"])
            self.assertNotEqual(previous["body_sha256"], replaced["body_sha256"])
            history = report.parent / "历史" / f"chapter-001-{previous['body_sha256'][:12]}.json"
            self.assertEqual(previous, json.loads(history.read_text(encoding="utf-8")))

    def test_project_title_rejects_explicit_author_or_pen_name_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            invalid = base / "invalid"
            _, init_error = run_script(
                "init_project.py",
                "--project-root",
                invalid,
                "--title",
                "潮汐钟楼 某某著",
                "--scope",
                "short",
                "--complexity",
                "light",
                "--primary-driver",
                "experiential",
                expect=2,
            )
            self.assertFalse(init_error["ok"])
            self.assertIn("疑似混入作者", init_error["error"])
            self.assertFalse(invalid.exists())

            project = base / "valid"
            self.init_project(project, "short", "light", "experiential")
            work = project / "作品.md"
            polluted = work.read_text(encoding="utf-8").replace(
                'title: "short-测试书"', 'title: "short-测试书 作者：某某"'
            )
            write(work, polluted)
            _, validation = run_script("validate_project.py", "--project-root", project, expect=1)
            self.assertTrue(any("疑似混入作者" in error for error in validation["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
