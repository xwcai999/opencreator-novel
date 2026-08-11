# 方法来源、许可证与安全边界

## 来源记录

| 来源 | 许可证状态 | 采用的方法思想 | 本 Skill 的处理 |
| --- | --- | --- | --- |
| [Novel Control Station](https://github.com/jingtai123/Novel-Control-Station-Skill) | MIT，仓库含许可证 | 人物压力、章节结构、对话压力、去分析腔、真实性修订 | 重新组织并用中文独立表述；未复制自动续写脚本 |
| [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | Apache-2.0 | 读者奖励、首次读者模拟、人物声音、逆向审稿 | 独立重写工作流；未复制其英文文本分析器 |
| [worldwonderer/oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) | MIT，仓库含许可证 | `story-deslop` 的只读候选扫描、分阶段真实性修订和修后复查 | 独立实现保守的 Python 扫描器；未复制其 JavaScript 规则、Hook、Agent、状态系统或禁用词表 |
| [blader/humanizer](https://github.com/blader/humanizer) | MIT，仓库含许可证 | 以作者样本校准声音、禁止捏造事实、改后再次审查 | 只采用通用原则；未复制其英文模式清单和示例文本 |
| [leenbj/novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | README 声称 MIT，但仓库未见完整 LICENSE，视为授权不完整 | 阶段审查、事件轮换、防止矛盾过早解决 | 只吸收抽象思想并独立实现；不复制代码和受表达保护的文本 |

本地实现继续保留来源记录，不把“本地运行”当作忽略许可证的理由。许可证不明确的来源只能提供思路线索。

## 明确排除

- Novel Control Station 中带 `--dangerously-bypass-approvals-and-sandbox` 的自动续写脚本。
- leenbj 项目中的外部模型 Provider、API Key、联网调用、安装/覆盖脚本和额外状态系统。
- haowjy 的英文专用 `analyze.py`；中文分析器在本 Skill 中使用 Python 标准库独立实现。
- `oh-story-claudecode` 的整套安装、Hook、Agent、第二套项目结构，以及把破折号或固定句式命中直接当作硬错误的策略。
- `humanizer` 的英文写作黑名单、为通过检测器而改写的目标，以及脱离小说连续性的全篇统一重写。
- 强制章章悬念、未解决问题、固定对白比例、固定冲突数、固定情绪公式和统一三幕结构。
- 任何第二套权威真值、隐藏外部依赖、权限绕过或未经确认的正文覆盖。

## 写入与执行边界

- 项目脚本只写用户指定的新项目、迁移目标、索引/报告派生目录或明确的 Skill 暂存目录。
- `validate_project.py`、`retrieve_context.py`、`analyze_prose_trends.py` 和 `scan_authenticity_artifacts.py` 只读。
- 迁移源目录始终只读，目标必须不存在或为空。
- 封面生成只通过用户指定的 `$codex-gpt-image` 工作流；不在本 Skill 中处理或保存凭据。
- 不提供递归删除、宽泛覆盖、危险安装、自动联网或外部模型执行脚本。

## 本地依赖

- 项目初始化、迁移、校验、索引、检索、上下文包、文体分析和真实性扫描使用 Python 标准库。
- 新封面工作流不再使用 Pillow 排版书名；书名与画面由 `$codex-gpt-image` 一次生成。`render_cover_title.py` 仅保留旧项目兼容，其 `deterministic-overlay` 产物不能通过新封面校验。
- `$codex-gpt-image` 是用户指定的封面生成 Skill，不作为本目录脚本的隐藏网络依赖，也不在此处读取认证信息。
