# OpenCreator Novel

[中文 README](README.zh-CN.md)

OpenCreator Novel is the fiction member of the [OpenCreator](https://github.com/xwcai999/opencreator) ecosystem. Its installed plugin remains `novel-studio-skill`, and its compatible Skill invocation remains `$novel-studio`. It plans, drafts, continues, revises, reviews, migrates, and packages Chinese fiction while keeping indexes, context packs, metrics, and review reports reproducible and separate from the manuscript.

## What it provides

- **Planning:** reader contract, one primary (and optional secondary) narrative driver, scope/complexity selection, synopsis, book/volume/chapter outlines, and concrete early-chapter promises.
- **Drafting and continuation:** chapter control cards, fixed-writer sequencing, pressure-driven character choices, and a reader-visible return in every chapter. The workflow does not force a mystery, cliffhanger, reversal, or fixed chapter length when the story does not need one.
- **Continuity management:** Markdown plus frontmatter are authoritative. The expectation ledger tracks planted, reinforced, active, partial, fulfilled, and dropped promises; context packs and deterministic retrieval make required sources explicit before continuation.
- **Review and revision:** deterministic project validation, chapter acceptance evidence, reader/style review, stage review, prose-trend evidence, and conservative authenticity-revision candidates. Reports never overwrite manuscript facts.
- **Migration and delivery:** safe migration from an older `novel-planner` project, isolated derived output, publication-readiness pilots, blind full-text checks, and submission-oriented packaging guidance.
- **Covers:** an optional `$codex-gpt-image` workflow can generate the complete cover and title in one model-native image. The skill does not read or store OAuth credentials; the legacy local title-overlay script is not the current cover path.

The included Python tools are small, deterministic command-line utilities. The model-orchestration rules live in [`plugins/novel-studio-skill/skills/novel-studio/SKILL.md`](plugins/novel-studio-skill/skills/novel-studio/SKILL.md) and its directly linked references.

## Why use it

Novel work accumulates facts faster than a chat transcript can reliably remember them. OpenCreator Novel makes those facts inspectable: the manuscript and frontmatter remain authoritative, while indexes, reports, and context packs are derived evidence that can be rebuilt. The ledger catches premature or forgotten promises; validation and acceptance records make hand-offs auditable; and the review workflow separates hard errors, reading blockers, and craft warnings instead of hiding them in a score.

This is guidance and tooling, not an automatic quality or publication guarantee. A human still owns the creative direction, final edits, and any external submission decision.

See the bilingual [Privacy Policy](PRIVACY.md), [Terms of Use](TERMS.md), and [Security Policy](SECURITY.md) before public or team deployment.

## Installation

### Codex plugin installation

1. Add this repository as a pinned marketplace: `codex plugin marketplace add xwcai999/opencreator-novel --ref v0.2.0`.
2. Install the plugin: `codex plugin add novel-studio-skill@novel-studio-community`.
3. Start a new Codex session so the plugin registry reloads.
4. Invoke the skill with `$novel-studio` and describe the novel task. The default interface prompt is also recorded in [`plugins/novel-studio-skill/skills/novel-studio/agents/openai.yaml`](plugins/novel-studio-skill/skills/novel-studio/agents/openai.yaml).

For local development, clone the repository and register its root as a marketplace. Keep `plugins/novel-studio-skill/.codex-plugin/plugin.json` and its sibling `skills/` directory together.

### Standalone installation

No plugin manager is required. Copy `plugins/novel-studio-skill/skills/novel-studio/` into the skills directory used by your Codex-compatible host, preserving `SKILL.md`, `references/`, `scripts/`, `assets/`, and `agents/`. Point your host at that skill (or include the `SKILL.md` instructions in your local workflow), then run the scripts from the copied directory. The `.codex-plugin` manifest is only needed for plugin discovery.

For direct script use:

```powershell
cd path/to/novel-studio
python scripts/init_project.py --project-root path/to/book --title "书名" --scope short --complexity light --primary-driver experiential
python scripts/validate_project.py --project-root path/to/book
```

The same commands work from a POSIX shell after replacing the paths. `init_project.py` refuses a non-empty target; use a new or empty directory for initialization and migration.

## Requirements and optional dependencies

- **Python 3.10 or newer.** The core scripts use the Python standard library (`argparse`, `pathlib`, `json`, `re`, hashing, and filesystem primitives); there is no required runtime package list for the project/continuity tools.
- **PyYAML (optional).** Frontmatter parsing uses `yaml.safe_load` when PyYAML is available. Without it, the bundled fallback parser handles the simple frontmatter emitted by the templates. Install PyYAML if your project uses richer YAML syntax; it is not a hidden network dependency.
- **Pillow (legacy only).** The current cover workflow does not use Pillow. `scripts/render_cover_title.py` is retained for old projects and local title-overlay compatibility; its post-render overlay is not accepted by the current native-title cover gate. Pillow may also be needed only when running tests that exercise that legacy image path.
- **`$codex-gpt-image` and Codex OAuth (optional).** They are needed only when you explicitly request the model-native cover workflow. The skill's scripts neither call an external image API nor handle OAuth tokens.

## Core command map

Run commands from `plugins/novel-studio-skill/skills/novel-studio/`:

| Goal | Command |
| --- | --- |
| Initialize a new project | `python scripts/init_project.py --project-root <dir> --title "<title>" --scope short --complexity light --primary-driver experiential` |
| Validate project structure and ledgers | `python scripts/validate_project.py --project-root <dir>` |
| Rebuild the deterministic index | `python scripts/reindex_project.py --project-root <dir>` |
| Audit promises before continuing | `python scripts/expectation_ledger.py --project-root <dir> --target-chapter <n>` |
| Build a derived context pack | `python scripts/build_context_pack.py --project-root <dir> --chapter <n> --query "<question>"` |
| Retrieve continuity sources | `python scripts/retrieve_context.py --project-root <dir> --query "<question>" --top-k 6` |
| Scan a manuscript for publication-risk candidates (read-only) | `python scripts/analyze_publication_risk.py <file-or-dir>` |
| Record accepted chapter evidence | `python scripts/record_chapter_review.py --project-root <dir> --chapter <n> --rounds 1 --author-passed --reader-passed --style-passed --rereview-passed` |
| Migrate without changing the source | `python scripts/migrate_project.py --source <old-dir> --target <new-dir> --title "<title>"` |

`retrieve_context.py` is deterministic term/entity retrieval, not semantic-vector RAG. Trend and authenticity scanners return evidence or candidates for human/model review; they do not decide literary quality, authorship, or plagiarism.

Full continuity validation requires the v2 project layout described in `references/project-schema.md`. A standalone TXT/Markdown manuscript can be reviewed read-only, but it is not silently converted and cannot receive project-level continuity or publication-readiness certification. `migrate_project.py` supports legacy `novel-planner` projects only; any other normalization requires explicit user approval and a new directory. No bundled command independently certifies a manuscript as publication-ready.

## Project layout

```text
opencreator-novel/
├── .agents/plugins/marketplace.json # repository marketplace
├── plugins/novel-studio-skill/
│   ├── .codex-plugin/plugin.json    # plugin manifest
│   └── skills/novel-studio/
│       ├── SKILL.md                # workflow contract and routing
│       ├── agents/openai.yaml      # display name and default prompt
│       ├── references/              # planning, chapter, review, schema, cover, and source notes
│       ├── scripts/                 # deterministic Python tools
│       └── assets/project-template/ # new-project Markdown templates
├── tests/                           # repository test suite, excluded from the installed plugin
├── THIRD_PARTY_NOTICES.md          # third-party methods and license notes
├── README.md
└── README.zh-CN.md
```

Within a novel project, Markdown/frontmatter are the authority. `索引/`, `报告/`, and other generated context or analysis outputs are derived and must not be used to overwrite the manuscript. See [`plugins/novel-studio-skill/skills/novel-studio/references/project-schema.md`](plugins/novel-studio-skill/skills/novel-studio/references/project-schema.md) for the exact schema and write boundaries.

## Copyable prompts

Each prompt can be pasted into a Codex session after the plugin is loaded.

1. `Use $novel-studio to start a short Chinese novel titled “<title>”. Choose the primary narrative driver, define the reader contract, and return the premise, tags, synopsis, and the first three chapter control cards before drafting.`
2. `Use $novel-studio to turn this existing outline into a medium-length project. Preserve every stated fact, choose scope and complexity, and identify which promises belong in the expectation ledger: <paste outline>.`
3. `Use $novel-studio to continue chapter <n>. Audit 状态/待兑现.md first, build the required context pack, and draft the next chapter with a concrete character choice, cost, and reader-visible return. Do not add filler after the climax.`
4. `Use $novel-studio to revise this chapter. List hard errors, reading blockers, and craft warnings separately; make only causally justified changes, then run the reader/style/authenticity checks again: <paste chapter>.`
5. `Use $novel-studio to migrate the old project at <source> to a new empty directory at <target>. Keep the source read-only, report any compatibility warnings, and do not copy unverified cover assets.`
6. `Use $novel-studio to prepare this long-form manuscript for publication-readiness review. Run the automatic trial-writing gate, stage blind review, and final plain-text checks; stop and report the first blocking failure instead of claiming approval: <project path>.`
7. `Use $novel-studio to create a cover through $codex-gpt-image for the exact title in 作品.md. Generate the complete image with model-native title text, no pen name, author credit, logo, watermark, or extra slogan, and report the verification evidence without exposing OAuth tokens.`

## Privacy, safety, and limits

- The bundled scripts operate on paths you provide and do not automatically upload manuscripts, browse the web, install packages, delete directories, or execute external model providers. Migration reads the source and writes only to a new/empty target; validation and retrieval tools are read-only apart from their documented derived outputs.
- A Codex host may send prompts or manuscript excerpts to the model/account selected for that session. Review your host's data controls before using private or unpublished material; this README does not change the host's retention or training policy.
- Cover generation is opt-in. `$codex-gpt-image`/Codex OAuth is used only when you request it, and credentials remain under the host's control. Do not paste tokens into project files or reports.
- No script promises literary quality, platform acceptance, readership, or any other outcome. Publication, legal clearance, copyright review, and external submission remain your responsibility.
- The authenticity workflow is a conservative revision aid, not an AI detector, plagiarism checker, or method for evading detection. Human/contextual judgment is required before accepting a candidate change.
- The project intentionally avoids a second hidden source of truth, permission bypasses, dangerous recursive operations, forced chapter formulas, and automatic manuscript overwrites.

## OpenCreator ecosystem

This repository follows OpenCreator's shared contract: source code stays separate from user works and runtime evidence; secrets remain outside Git; derived artifacts are rebuildable; external publishing requires human confirmation; and English and Simplified Chinese documentation stay aligned. The sibling projects are [OpenCreator Music](https://github.com/xwcai999/opencreator-music), [OpenCreator Dashboard](https://github.com/xwcai999/opencreator-dashboard), and [OpenCreator Family Video](https://github.com/xwcai999/opencreator-family-video).

## Third-party method references

The method audit is summarized in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and recorded in [`plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md`](plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md):

| Reference | License/status | Use in this skill |
| --- | --- | --- |
| [Novel Control Station](https://github.com/jingtai123/Novel-Control-Station-Skill) | MIT | Abstract ideas about character pressure, chapter structure, dialogue pressure, and authenticity revision; independently reorganized. |
| [creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | Apache-2.0 | Reader rewards, first-reader simulation, character voice, and reverse review; independently rewritten. |
| [oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) | MIT | Read-only candidate scanning and staged authenticity revision; no JavaScript rules, hooks, agents, or state system copied. |
| [humanizer](https://github.com/blader/humanizer) | MIT | General principles for sample-based voice calibration and re-review; no English pattern list or examples copied. |
| [novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | README claims MIT, but no full license file was found; license evidence incomplete | Abstract ideas only (stage review, event rotation, and avoiding premature resolution); no protected expression or code copied. |

This project is not affiliated with, endorsed by, or sponsored by OpenAI. “OpenAI”, “Codex”, and “GPT” are trademarks or product names of their respective owners; references here describe optional host integrations, not an official OpenAI distribution.
