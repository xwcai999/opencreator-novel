from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "plugins" / "novel-studio-skill" / "skills" / "novel-studio"
SKILL_TEXT = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
MODULES = (
    "character-arc.md",
    "dialogue-pov.md",
    "pacing-genre.md",
    "revision-cases.md",
    "scene-craft.md",
    "world-faction-dynamics.md",
    "fullbook-review.md",
    "structure-similarity-review.md",
)


class CreativeModuleContractTests(unittest.TestCase):
    def test_modules_exist_and_are_directly_reachable(self) -> None:
        for name in MODULES:
            self.assertTrue((SKILL_ROOT / "references" / name).is_file(), name)
            self.assertIn(f"references/{name}", SKILL_TEXT, name)

    def test_progressive_loading_is_explicit(self) -> None:
        self.assertIn("不要每次把全部创作参考装入上下文", SKILL_TEXT)
        self.assertIn("修订根因不清、跨章复现或最小修订失败时再读", SKILL_TEXT)

    def test_existing_safety_contracts_are_preserved(self) -> None:
        self.assertIn("审查普通 TXT/Markdown 或非 v2 项目时默认只读", SKILL_TEXT)
        self.assertIn("封面路由的可选外部依赖", SKILL_TEXT)
        self.assertIn("投稿型每 5–6 章自动纯正文阶段盲读", SKILL_TEXT)
        self.assertIn("非投稿型每 8–10 章", SKILL_TEXT)
        self.assertIn("同一根因层最多连续两轮", SKILL_TEXT)

    def test_fullbook_routes_are_public(self) -> None:
        self.assertIn("完本复评、全本评分、终稿文学验收", SKILL_TEXT)


if __name__ == "__main__":
    unittest.main()
