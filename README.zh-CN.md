# OpenCreator Novel

[English README](README.md)

> 预览分支：新增人物弧光、场景设计、对白/视角、节奏、修订案例和世界/势力离屏运转模块；这不是稳定版本。

OpenCreator Novel 是 [OpenCreator](https://github.com/xwcai999/opencreator) 生态的小说成员。为保持兼容，安装后的插件仍叫 `novel-studio-skill`，其中包含三个可分别调用的 Skill：`$novel-studio` 负责小说工作流，`$wawa-submission` 负责非官方离线投稿材料预检，`$wawa-source` 负责校验、脱敏并聚合用户提供的蛙蛙统计快照。两个蛙蛙 Skill 都可单独安装和使用。

## 能力概览

- **规划：**读者契约、一个主叙事驱动（可选副驱动）、篇幅/复杂度选择、简介、总纲/卷纲/章纲，以及前三章的具体承诺。
- **写作与续写：**章节控制卡、固定主笔顺序、压力下的人物选择与代价，以及每章可感知的读者回报。故事不需要时，不强制谜团、章末悬念、反转、固定章节长度或统一公式。
- **连续性管理：**Markdown 与 frontmatter 是权威事实。待兑现台账追踪 `planted`、`reinforced`、`active`、`partial`、`fulfilled`、`dropped` 等状态；上下文包和确定性检索让续写前必须读取的来源可见。
- **审查与修订：**确定性项目校验、章节接受证据、读者/文风审查、阶段审查、文体趋势证据和保守的真实性修订候选。报告不会回写或覆盖正文事实。
- **迁移与交付：**从旧 `novel-planner` 项目安全迁移，隔离派生输出，投稿准备试写、纯正文盲读和面向投稿的包装指导。
- **封面：**可选的 `$codex-gpt-image` 工作流一次生成完整画面和书名。Skill 不读取或保存 OAuth 凭据；旧的本地叠字脚本不属于当前封面路径。
- **蛙蛙投稿适配（非官方）：**整理可复制材料单并执行本地文件/字段预检。集成模式可复用 Novel Studio 项目证据；独立模式只需要元数据和稿件。内置版本化的离线分类/标签快照用于确定性预检，当前页面仍是最终依据。它不会登录、上传、勾选协议或提交。
- **蛙蛙统计数据源（非官方）：**校验本地 `wawa.stats.v1` JSON、检查快照时效、移除作品/账号标识，并生成聚合 JSON 或 Dashboard 契约。它不会打开蛙蛙、登录、抓取页面或采集实时数据。

内置 Python 工具是小型、确定性的命令行程序；模型编排规则位于 [`plugins/novel-studio-skill/skills/novel-studio/SKILL.md`](plugins/novel-studio-skill/skills/novel-studio/SKILL.md) 及其直接链接的参考文件中。

## 为什么有用

小说项目积累事实的速度，往往超过聊天记录可靠记忆的能力。OpenCreator Novel 将事实变得可检查：正文和 frontmatter 保持权威，索引、报告和上下文包则是可重建的派生证据。待兑现台账能发现过早兑现或长期遗忘的承诺；项目校验与接受记录让交接可审计；审查按硬错误、阅读阻断项和工艺警告分层，而不是用单一分数掩盖问题。

这是工作流指导与工具，不是自动质量或投稿保证。创作方向、最终改稿以及任何外部提交决策仍由人负责。

公开或团队部署前，请阅读双语[隐私政策](PRIVACY.md)、[使用条款](TERMS.md)与[安全政策](SECURITY.md)。

## 安装

### 作为 Codex 插件安装

1. 按固定版本添加本仓库市场：`codex plugin marketplace add xwcai999/opencreator-novel --ref preview/novel-studio-0.6.0`。
2. 安装插件：`codex plugin add novel-studio-skill@novel-studio-community`。
3. 新建一个 Codex 会话，让插件注册表重新加载。
4. 小说创作使用 `$novel-studio`；材料整理使用 `$wawa-submission`；离线统计快照使用 `$wawa-source`。

本地开发时，可克隆仓库并把仓库根目录注册为 marketplace。请保持 `plugins/novel-studio-skill/.codex-plugin/plugin.json` 与同级 `skills/` 目录完整。

### Standalone 安装

不需要插件管理器。将 `plugins/novel-studio-skill/skills/novel-studio/` 复制到 Codex 兼容宿主使用的 skills 目录，并保留 `SKILL.md`、`references/`、`scripts/`、`assets/` 和 `agents/`。让宿主指向该 Skill（或在本地工作流中加载 `SKILL.md`），再从复制后的目录运行脚本。只有进行插件发现时才需要 `.codex-plugin` 清单。

如果只使用蛙蛙适配器，可单独复制 `plugins/novel-studio-skill/skills/wawa-submission/`。独立模式不依赖 `$novel-studio`，只需提供元数据 JSON 与真实的本地 `.txt` 或 `.docx` 稿件。旧式 `.doc` 无法由标准库可靠解析，因此会明确阻断并要求转换格式。

```powershell
cd path/to/wawa-submission
python scripts/validate_submission.py --metadata path/to/metadata.json --manuscript path/to/manuscript.txt --json
```

本适配器与蛙蛙写作无隶属或背书关系。本地通过不代表上传接受、审核通过或正式签约。`wawa-categories.json` 提供 350 条固定三级路径，`wawa-tags.json` 提供 158 个固定标签候选，二者都是版本化离线参考，不是蛙蛙 API 或永久平台规则。当前公开投稿页提示长篇达到 10 万字方可正式签约；历史 2 万/3 万字表单观察值只作为已过期风险提示保留。三者不得合并为签约保证，真实投稿前必须重新核对当前页面。

从 `v0.4.x` 升级时需注意：`categories` 现在必须精确匹配固定三级路径，`tags` 只填写固定平台标签；作者自定义标签迁移到 `custom_tags` 并等待页面确认。快照外的旧值会失败关闭，不会被静默替换成相似词。

如果只使用统计数据源，可单独复制 `plugins/novel-studio-skill/skills/wawa-source/`。输入必须是用户自行导出或整理的本地快照；公开项目有意不包含任何已登录采集器。

```powershell
cd path/to/wawa-source
python scripts/wawa_snapshot.py validate path/to/snapshot.json --json
python scripts/wawa_snapshot.py aggregate path/to/snapshot.json --json
python scripts/wawa_snapshot.py dashboard path/to/snapshot.json --days 30 --json
```

未知指标保持 `null`，且不会进入 `availableMetrics`，绝不伪造为 0。Dashboard 输出只有聚合值，不包含作品名、远端 ID、账号、Cookie、令牌或浏览器会话数据。

直接运行脚本示例：

```powershell
cd path/to/novel-studio
python scripts/init_project.py --project-root path/to/book --title "书名" --scope short --complexity light --primary-driver experiential
python scripts/validate_project.py --project-root path/to/book
```

在 POSIX shell 中将路径替换为对应写法即可。`init_project.py` 会拒绝非空目标；初始化或迁移请使用新建或空目录。

## 运行要求与可选依赖

- **Python 3.10 或更高版本。**核心脚本使用 Python 标准库（`argparse`、`pathlib`、`json`、`re`、哈希与文件系统原语）；项目/连续性工具没有必需的运行时第三方包清单。
- **PyYAML（可选）。**有 PyYAML 时，frontmatter 使用 `yaml.safe_load`；没有时使用内置回退解析器，能够处理模板生成的简单 frontmatter。若项目使用更丰富的 YAML 语法，建议安装 PyYAML；它不是隐藏的联网依赖。
- **Pillow（仅 legacy）。**当前封面工作流不使用 Pillow。`scripts/render_cover_title.py` 仅为旧项目和本地叠字兼容保留，其后期叠字结果不能通过当前原生书名封面门禁。只有运行覆盖该旧图像路径的测试时，才可能需要 Pillow。
- **`$codex-gpt-image` 与 Codex OAuth（可选）。**仅在明确请求模型原生封面工作流时需要。Skill 脚本不会调用外部图片 API，也不会处理 OAuth token。

## 核心命令速查

从 `plugins/novel-studio-skill/skills/novel-studio/` 目录运行：

| 目标 | 命令 |
| --- | --- |
| 初始化新项目 | `python scripts/init_project.py --project-root <dir> --title "<title>" --scope short --complexity light --primary-driver experiential` |
| 校验项目结构与台账 | `python scripts/validate_project.py --project-root <dir>` |
| 重建确定性索引 | `python scripts/reindex_project.py --project-root <dir>` |
| 续写前审计承诺 | `python scripts/expectation_ledger.py --project-root <dir> --target-chapter <n>` |
| 构建派生上下文包 | `python scripts/build_context_pack.py --project-root <dir> --chapter <n> --query "<question>"` |
| 检索连续性来源 | `python scripts/retrieve_context.py --project-root <dir> --query "<question>" --top-k 6` |
| 只读扫描稿件的出版风险候选 | `python scripts/analyze_publication_risk.py <file-or-dir>` |
| 记录章节接受证据 | `python scripts/record_chapter_review.py --project-root <dir> --chapter <n> --rounds 1 --author-passed --reader-passed --style-passed --rereview-passed` |
| 不改源目录地迁移 | `python scripts/migrate_project.py --source <old-dir> --target <new-dir> --title "<title>"` |

`retrieve_context.py` 是确定性的词项/实体检索，不是语义向量 RAG。文体趋势与真实性扫描器只输出证据或候选，不能判定文学质量、作者身份或抄袭。

完整连续性校验要求稿件符合 `references/project-schema.md` 定义的 v2 项目结构。单独的 TXT/Markdown 可以只读审查，但不会被静默转换，也不能直接获得项目级连续性或“出版就绪”认证。`migrate_project.py` 只支持旧 `novel-planner` 项目；其他规范化必须先获得用户明确授权，并写入新目录。仓库内没有任何单一命令能够独立认证稿件已达到出版就绪状态。

## 目录结构

```text
opencreator-novel/
├── .agents/plugins/marketplace.json # 仓库 marketplace 清单
├── plugins/novel-studio-skill/
│   ├── .codex-plugin/plugin.json    # 插件清单
│   └── skills/
│       ├── novel-studio/             # 完整小说工作流
│       ├── wawa-submission/          # 可独立或集成使用的离线适配器
│       └── wawa-source/              # 可独立使用的离线统计快照适配器
├── tests/                           # 仓库测试，不进入安装插件
├── THIRD_PARTY_NOTICES.md          # 第三方方法与许可证说明
├── README.md
└── README.zh-CN.md
```

在小说项目内，Markdown/frontmatter 是权威来源。`索引/`、`报告/` 以及其他上下文或分析输出都是派生物，不能用来覆盖正文。准确的结构和写入边界见 [`plugins/novel-studio-skill/skills/novel-studio/references/project-schema.md`](plugins/novel-studio-skill/skills/novel-studio/references/project-schema.md)。

## 可复制提示词

插件加载后，可将以下提示词直接粘贴到 Codex 会话中。

1. `使用 $novel-studio 开始一部名为“<书名>”的中文短篇小说。选择主叙事驱动，定义读者契约，输出前提、标签、简介和前三章控制卡，然后再写正文。`
2. `使用 $novel-studio 将下面的现有大纲整理成中篇项目。保留所有已给事实，选择篇幅与复杂度，并标出哪些承诺应写入待兑现台账：<粘贴大纲>。`
3. `使用 $novel-studio 续写第 <n> 章。先审计 状态/待兑现.md，构建必需的上下文包，再写出包含具体人物选择、代价和读者回报的下一章；高潮后不要用复盘或表格凑字。`
4. `使用 $novel-studio 修订这一章。分别列出硬错误、阅读阻断项和工艺警告；只做有因果依据的最小改动，然后重新运行读者、文风和真实性审查：<粘贴章节>。`
5. `使用 $novel-studio 将旧项目 <源目录> 迁移到新的空目录 <目标目录>。保持源目录只读，报告兼容性警告，不复制未经验证的封面资源。`
6. `使用 $novel-studio 为这部长篇执行投稿准备审查。运行自动试写门禁、阶段纯正文盲读和最终纯文本检查；遇到第一个阻断失败就停止并报告，不要声称已通过：<项目路径>。`
7. `使用 $novel-studio 通过 $codex-gpt-image 为 作品.md 中的规范书名制作封面。一次生成完整画面和模型原生书名文字，不要笔名、作者署名、Logo、水印或额外宣传语；报告验证证据，但不要暴露 OAuth token。`
8. `使用 $wawa-submission 的独立模式预检这份元数据 JSON 和稿件。不要调用 $novel-studio，不要登录、上传或声称平台已接受：<路径>。`
9. `使用 $wawa-submission 的集成模式处理这个 Novel Studio 项目。复用既有项目证据，列出全部待用户确认字段，并将缓存规则与当前页面证据分开：<项目路径>。`
10. `使用 $wawa-source 校验并脱敏这份用户提供的 wawa.stats.v1 快照，然后导出 30 天 Dashboard 聚合数据。不要联网，也不要把缺失指标推断为 0：<快照路径>。`

## 隐私、安全与限制

- 内置脚本只操作你提供的路径，不会自动上传正文、联网浏览、安装包、删除目录或执行外部模型 Provider。迁移只读源目录并写入新建/空目标；校验与检索除文档化的派生输出外均为只读。
- Codex 宿主可能把本次会话的提示词或正文片段发送给所选模型/账户。处理私人或未发表内容前，请检查宿主的数据控制；本 README 不会改变宿主的留存或训练政策。
- 封面生成是可选操作。只有你请求时才使用 `$codex-gpt-image`/Codex OAuth，凭据仍由宿主控制。不要把 token 粘贴进项目文件或报告。
- 任何脚本都不保证文学质量、平台接受或其他结果。投稿、法律清理、版权审查与外部提交仍由你负责。
- 蛙蛙支持是离线、非官方能力。本仓库不包含已登录采集器、浏览器 Profile、平台会话或实时抓取工作流；`$wawa-source` 只接受用户提供的本地快照。
- 真实性流程是保守的修订辅助，不是 AI 检测器、抄袭检查器，也不是规避检测的方法。接受候选改动前必须结合上下文进行人工判断。
- 项目刻意避免第二套隐藏真值、权限绕过、危险递归操作、强制章节公式和自动覆盖正文。

## OpenCreator 生态

本仓库遵循 OpenCreator 的共享契约：源代码与用户作品、运行证据分离；密钥不进入 Git；派生文件可重建；对外发布必须人工确认；英文与简体中文说明保持同步。兄弟项目包括 [OpenCreator Music](https://github.com/xwcai999/opencreator-music)、[OpenCreator Dashboard](https://github.com/xwcai999/opencreator-dashboard) 和 [OpenCreator Family Video](https://github.com/xwcai999/opencreator-family-video)。

## 第三方方法参考

方法审计汇总在 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)，并记录于 [`plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md`](plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md)：

| 参考来源 | 许可证/状态 | 本 Skill 的使用方式 |
| --- | --- | --- |
| [Novel Control Station](https://github.com/jingtai123/Novel-Control-Station-Skill) | MIT | 采用人物压力、章节结构、对话压力与真实性修订等抽象思想，重新组织并独立表述。 |
| [creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | Apache-2.0 | 采用读者回报、首次读者模拟、人物声音和逆向审稿，工作流独立重写。 |
| [oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) | MIT | 采用只读候选扫描和分阶段真实性修订；未复制其 JavaScript 规则、Hook、Agent 或状态系统。 |
| [humanizer](https://github.com/blader/humanizer) | MIT | 仅采用样本校准文风与改后复审的一般原则，未复制英文模式清单或示例文本。 |
| [novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | README 声称 MIT，但未找到完整许可证文件；许可证证据不完整 | 仅参考阶段审查、事件轮换和避免过早解决等抽象思想；未复制受保护表达或代码。 |

本项目与 OpenAI 无隶属、背书或赞助关系。“OpenAI”“Codex”“GPT”是其各自权利人的商标或产品名称；这里仅描述可选的宿主集成，不代表 OpenAI 官方发行版。
