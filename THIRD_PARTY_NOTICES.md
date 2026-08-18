# 第三方方法来源与通知

本文件记录 OpenCreator Novel（内部 Skill 名 `novel-studio`）参考过的五个公开项目、其公开许可证信息和仅限于抽象方法层面的采用情况。来源记录以 [`plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md`](plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md) 为准；本文件不是法律意见。

当前仓库没有把下列项目作为运行时依赖，也没有把其代码、受表达保护的文本、规则文件或示例打包进来。许可证状态按查阅到的仓库内容记录；许可证不完整的来源不会被当作可再分发依赖。

## 蛙蛙写作平台事实来源

`wawa-submission` 与 `wawa-source` 仅为互操作说明而引用“蛙蛙写作”名称和公开投稿 URL。蛙蛙写作不是本项目的运行时依赖、许可方、赞助方或背书方。本仓库不分发其 Logo、截图、网页 HTML、协议原文、采集器、浏览器会话或私有平台素材；动态类目、标签、限制、签约提示及统计字段均以平台当前页面与条款为准。统计示例全部为虚构数据。

| 来源（URL） | 声明的许可证状态 | 采用的抽象方法 | 未复制/明确排除内容 |
| --- | --- | --- | --- |
| [Novel Control Station](https://github.com/jingtai123/Novel-Control-Station-Skill) | MIT；来源仓库含许可证文件 | 人物压力、章节结构、对话压力、去分析腔和真实性修订 | 未复制自动续写脚本；明确排除带 `--dangerously-bypass-approvals-and-sandbox` 的脚本及任何权限绕过行为 |
| [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | Apache-2.0 | 读者奖励、首次读者模拟、人物声音和逆向审稿 | 独立重写工作流；未复制英文 `analyze.py` 或其英文文本分析器 |
| [worldwonderer/oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) | MIT；来源仓库含许可证文件 | `story-deslop` 的只读候选扫描、分阶段真实性修订和修后复查 | 未复制 JavaScript 规则、Hook、Agent、状态系统或禁用词表；未引入其整套安装流程 |
| [blader/humanizer](https://github.com/blader/humanizer) | MIT；来源仓库含许可证文件 | 以作者样本校准声音、禁止捏造事实、修改后再次审查 | 只采用通用原则；未复制英文模式清单、示例文本或以通过检测器为目标的改写策略 |
| [leenbj/novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | README 声称 MIT，但仓库未见完整 `LICENSE`；许可证证据不完整 | 阶段审查、事件轮换和避免矛盾过早解决 | 仅吸收抽象思想；未复制任何代码或受表达保护的文本，不把它当可再分发依赖；明确排除外部模型 Provider、API Key、联网调用、安装/覆盖脚本和额外状态系统 |

## 处理原则

- 所有本地实现均按当前仓库的需求独立编写；抽象方法不等于复制实现或表达。
- 未明确授权的来源只提供思路线索。尤其是 `leenbj/novel-creator-skill`，许可证证据不完整，当前项目不分发其任何内容，也不在安装、构建或运行时下载它。
- 外部方法来源变化时，应先更新本文件和 `method-sources.md`，再评估是否仍可发布；不要把“本地运行”当作忽略许可证的理由。

---

# Third-party method references and notices

This section is the English counterpart of the Chinese notice above. OpenCreator Novel (internal Skill name `novel-studio`) does not bundle the following projects as runtime dependencies and does not redistribute their code, protected prose, rule files, or examples. License status is recorded from the repository evidence available at review time; an incomplete license claim is not treated as permission to redistribute.

| Source | Verified license status | Abstract methods considered | Content not copied / explicitly excluded |
| --- | --- | --- | --- |
| [Novel Control Station](https://github.com/jingtai123/Novel-Control-Station-Skill) | MIT; a complete `LICENSE` file was found | Character pressure, chapter structure, dialogue pressure, reducing analytical narration, and authenticity revision | No auto-continuation script was copied; scripts using `--dangerously-bypass-approvals-and-sandbox` and all approval-bypass behavior are explicitly excluded |
| [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | Apache-2.0; a complete `LICENSE` file was found | Reader rewards, first-reader simulation, character voice, and reverse review | The workflow was independently rewritten; the English `analyze.py` and its English text analyzer were not copied |
| [worldwonderer/oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) | MIT; a complete `LICENSE` file was found | Read-only candidate scanning, staged authenticity revision, and post-revision review inspired by `story-deslop` | No JavaScript rules, hooks, agents, state system, banned-word list, or full installer were copied |
| [blader/humanizer](https://github.com/blader/humanizer) | MIT; a complete `LICENSE` file was found | Sample-based voice calibration, avoiding invented facts, and reviewing a revision again | Only general principles were considered; no English pattern list, example prose, or detector-evasion objective was copied |
| [leenbj/novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | Its README claims MIT, but no complete `LICENSE`, `LICENSE.md`, or `COPYING` file was found; license evidence is incomplete | Stage review, event rotation, and avoiding premature conflict resolution | Abstract ideas only; no code or protected text was copied, and this project is not a redistributable dependency. External model providers, API keys, network calls, install/overwrite scripts, and extra state systems are explicitly excluded |

## English handling principles

- Implementations in this repository were written independently for this workflow; considering an abstract method is not the same as copying an implementation or protected expression.
- Sources without clear licensing evidence may provide research leads only. In particular, no content from `leenbj/novel-creator-skill` is distributed, downloaded, installed, built, or executed by this project.
- When an upstream source or license changes, update this notice and `plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md` before deciding whether a new release remains appropriate.
